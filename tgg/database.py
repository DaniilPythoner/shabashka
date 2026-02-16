# database.py
import sqlite3
import datetime
from typing import Optional, Dict, List, Tuple

class Database:
    def __init__(self, db_name: str = "dice_bot.db"):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        """Инициализация таблиц базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    balance INTEGER DEFAULT 1000,
                    referrer_id INTEGER,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_games INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    total_losses INTEGER DEFAULT 0,
                    total_bet_amount INTEGER DEFAULT 0,
                    total_win_amount INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    is_admin INTEGER DEFAULT 0
                )
            ''')
            
            # Таблица рефералов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referral_id INTEGER,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    bonus_given INTEGER DEFAULT 0,
                    FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                    FOREIGN KEY (referral_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица игр
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    game_type TEXT,
                    bet_amount INTEGER,
                    win_amount INTEGER,
                    result TEXT,
                    game_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица транзакций
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    transaction_type TEXT,
                    description TEXT,
                    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица ежедневных бонусов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_bonus (
                    user_id INTEGER,
                    last_claim DATE,
                    streak INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            conn.commit()
    
    # === РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ===
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, 
                 last_name: str = None, referrer_id: int = None) -> bool:
        """Добавление нового пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Проверяем, существует ли пользователь
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                if cursor.fetchone():
                    return False
                
                # Добавляем пользователя
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name, last_name, balance, referrer_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name, 1000, referrer_id))
                
                # Если есть реферер, начисляем бонусы
                if referrer_id:
                    # Проверяем, существует ли реферер
                    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
                    if cursor.fetchone():
                        # Начисляем бонус рефереру
                        cursor.execute('''
                            UPDATE users SET balance = balance + 100 WHERE user_id = ?
                        ''', (referrer_id,))
                        
                        # Начисляем бонус новому пользователю
                        cursor.execute('''
                            UPDATE users SET balance = balance + 50 WHERE user_id = ?
                        ''', (user_id,))
                        
                        # Записываем в таблицу рефералов
                        cursor.execute('''
                            INSERT INTO referrals (referrer_id, referral_id, bonus_given)
                            VALUES (?, ?, 1)
                        ''', (referrer_id, user_id))
                        
                        # Записываем транзакции
                        cursor.execute('''
                            INSERT INTO transactions (user_id, amount, transaction_type, description)
                            VALUES (?, ?, ?, ?)
                        ''', (referrer_id, 100, "referral_bonus", f"Бонус за приглашение пользователя {user_id}"))
                        
                        cursor.execute('''
                            INSERT INTO transactions (user_id, amount, transaction_type, description)
                            VALUES (?, ?, ?, ?)
                        ''', (user_id, 50, "referral_bonus", "Бонус за регистрацию по реферальной ссылке"))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Ошибка при добавлении пользователя: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, balance, referrer_id,
                       registration_date, last_activity, total_games, total_wins, 
                       total_losses, total_bet_amount, total_win_amount, is_banned, is_admin
                FROM users WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "user_id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "balance": row[4],
                    "referrer_id": row[5],
                    "registration_date": row[6],
                    "last_activity": row[7],
                    "total_games": row[8],
                    "total_wins": row[9],
                    "total_losses": row[10],
                    "total_bet_amount": row[11],
                    "total_win_amount": row[12],
                    "is_banned": row[13],
                    "is_admin": row[14]
                }
            return None
    
    def update_user_activity(self, user_id: int):
        """Обновление времени последней активности"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
    
    def update_balance(self, user_id: int, amount: int, transaction_type: str, description: str = "") -> bool:
        """
        Обновление баланса пользователя
        amount: положительное число - начисление, отрицательное - списание
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Получаем текущий баланс
                cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                
                if not result:
                    return False
                
                current_balance = result[0]
                new_balance = current_balance + amount
                
                # Проверяем, что баланс не отрицательный
                if new_balance < 0:
                    print(f"Ошибка: недостаточно средств. Текущий баланс: {current_balance}, попытка списать: {-amount}")
                    return False
                
                # Обновляем баланс
                cursor.execute('''
                    UPDATE users SET balance = ? WHERE user_id = ?
                ''', (new_balance, user_id))
                
                # Записываем транзакцию
                cursor.execute('''
                    INSERT INTO transactions (user_id, amount, transaction_type, description)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, amount, transaction_type, description))
                
                conn.commit()
                print(f"Баланс пользователя {user_id} изменен на {amount}. Новый баланс: {new_balance}")
                return True
        except Exception as e:
            print(f"Ошибка при обновлении баланса: {e}")
            return False
    
    # === СТАТИСТИКА ИГР ===
    
    def add_game_result(self, user_id: int, game_type: str, bet_amount: int, 
                        win_amount: int, result: str):
        """Добавление результата игры"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Добавляем запись об игре
            cursor.execute('''
                INSERT INTO games (user_id, game_type, bet_amount, win_amount, result)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, game_type, bet_amount, win_amount, result))
            
            # Обновляем статистику пользователя
            cursor.execute('''
                UPDATE users SET 
                    total_games = total_games + 1,
                    total_bet_amount = total_bet_amount + ?
                WHERE user_id = ?
            ''', (bet_amount, user_id))
            
            if win_amount > 0:
                cursor.execute('''
                    UPDATE users SET 
                        total_wins = total_wins + 1,
                        total_win_amount = total_win_amount + ?
                    WHERE user_id = ?
                ''', (win_amount, user_id))
            elif result == "loss":
                cursor.execute('''
                    UPDATE users SET total_losses = total_losses + 1 WHERE user_id = ?
                ''', (user_id,))
            
            conn.commit()
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Получение статистики пользователя"""
        user = self.get_user(user_id)
        if not user:
            return {}
        
        # Получаем дополнительную статистику
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Количество рефералов
            cursor.execute('''
                SELECT COUNT(*) FROM referrals WHERE referrer_id = ?
            ''', (user_id,))
            referrals_count = cursor.fetchone()[0]
            
            # Сумма выигрышей за все время
            cursor.execute('''
                SELECT SUM(win_amount) FROM games WHERE user_id = ? AND win_amount > 0
            ''', (user_id,))
            total_won = cursor.fetchone()[0] or 0
            
            # Сумма проигрышей
            cursor.execute('''
                SELECT SUM(bet_amount) FROM games WHERE user_id = ? AND result = 'loss'
            ''', (user_id,))
            total_lost = cursor.fetchone()[0] or 0
            
            # Любимая игра
            cursor.execute('''
                SELECT game_type, COUNT(*) as count FROM games 
                WHERE user_id = ? 
                GROUP BY game_type 
                ORDER BY count DESC 
                LIMIT 1
            ''', (user_id,))
            favorite_game_row = cursor.fetchone()
            favorite_game = favorite_game_row[0] if favorite_game_row else "Нет данных"
            
            return {
                **user,
                "referrals_count": referrals_count,
                "total_won": total_won,
                "total_lost": total_lost,
                "net_profit": total_won - total_lost,
                "favorite_game": favorite_game,
                "win_rate": (user["total_wins"] / user["total_games"] * 100) if user["total_games"] > 0 else 0
            }
    
    # === РЕФЕРАЛЬНАЯ СИСТЕМА ===
    
    def get_referrals(self, user_id: int) -> List[Dict]:
        """Получение списка рефералов пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.user_id, u.username, u.first_name, u.last_name, 
                       u.registration_date, u.total_games, r.bonus_given
                FROM referrals r
                JOIN users u ON r.referral_id = u.user_id
                WHERE r.referrer_id = ?
                ORDER BY r.registration_date DESC
            ''', (user_id,))
            
            rows = cursor.fetchall()
            referrals = []
            for row in rows:
                referrals.append({
                    "user_id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "registration_date": row[4],
                    "total_games": row[5],
                    "bonus_given": row[6]
                })
            return referrals
    
    # === АДМИН-ПАНЕЛЬ ===
    
    def get_all_users(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Получение списка всех пользователей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, balance, 
                       total_games, total_wins, registration_date, last_activity, is_banned
                FROM users
                ORDER BY balance DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            rows = cursor.fetchall()
            users = []
            for row in rows:
                users.append({
                    "user_id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "balance": row[4],
                    "total_games": row[5],
                    "total_wins": row[6],
                    "registration_date": row[7],
                    "last_activity": row[8],
                    "is_banned": row[9]
                })
            return users
    
    def get_total_users_count(self) -> int:
        """Получение общего количества пользователей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]
    
    def get_total_games_count(self) -> int:
        """Получение общего количества игр"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM games")
            return cursor.fetchone()[0]
    
    def get_total_bets_sum(self) -> int:
        """Получение общей суммы ставок"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(bet_amount) FROM games")
            return cursor.fetchone()[0] or 0
    
    def get_total_wins_sum(self) -> int:
        """Получение общей суммы выигрышей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(win_amount) FROM games")
            return cursor.fetchone()[0] or 0
    
    def get_top_players(self, limit: int = 10) -> List[Dict]:
        """Получение топ-игроков по балансу"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name, balance, total_games, total_wins
                FROM users
                WHERE is_banned = 0
                ORDER BY balance DESC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            players = []
            for i, row in enumerate(rows, 1):
                players.append({
                    "position": i,
                    "user_id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "balance": row[3],
                    "total_games": row[4],
                    "total_wins": row[5]
                })
            return players
    
    def ban_user(self, user_id: int) -> bool:
        """Блокировка пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET is_banned = 1 WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
                return True
        except Exception:
            return False
    
    def unban_user(self, user_id: int) -> bool:
        """Разблокировка пользователя"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET is_banned = 0 WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
                return True
        except Exception:
            return False
    
    def set_admin(self, user_id: int) -> bool:
        """Назначение администратора"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET is_admin = 1 WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
                return True
        except Exception:
            return False
    
    def remove_admin(self, user_id: int) -> bool:
        """Снятие администратора"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET is_admin = 0 WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
                return True
        except Exception:
            return False
    
    def get_daily_stats(self) -> Dict:
        """Получение статистики за сегодня"""
        today = datetime.date.today().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Новые пользователи сегодня
            cursor.execute('''
                SELECT COUNT(*) FROM users 
                WHERE DATE(registration_date) = ?
            ''', (today,))
            new_users = cursor.fetchone()[0]
            
            # Игр сегодня
            cursor.execute('''
                SELECT COUNT(*) FROM games 
                WHERE DATE(game_date) = ?
            ''', (today,))
            games_today = cursor.fetchone()[0]
            
            # Сумма ставок сегодня
            cursor.execute('''
                SELECT SUM(bet_amount) FROM games 
                WHERE DATE(game_date) = ?
            ''', (today,))
            bets_today = cursor.fetchone()[0] or 0
            
            # Сумма выигрышей сегодня
            cursor.execute('''
                SELECT SUM(win_amount) FROM games 
                WHERE DATE(game_date) = ? AND win_amount > 0
            ''', (today,))
            wins_today = cursor.fetchone()[0] or 0
            
            return {
                "new_users": new_users,
                "games_today": games_today,
                "bets_today": bets_today,
                "wins_today": wins_today,
                "profit_today": bets_today - wins_today
            }
    
    # === ЕЖЕДНЕВНЫЙ БОНУС ===
    
    def claim_daily_bonus(self, user_id: int) -> Optional[Dict]:
        """Получение ежедневного бонуса"""
        today = datetime.date.today().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, получал ли бонус сегодня
            cursor.execute('''
                SELECT last_claim, streak FROM daily_bonus WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            
            if row:
                last_claim, streak = row
                
                # Если уже получал сегодня
                if last_claim == today:
                    return None
                
                # Проверяем, была ли вчера
                yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
                if last_claim == yesterday:
                    streak += 1
                else:
                    streak = 1
                
                # Обновляем
                cursor.execute('''
                    UPDATE daily_bonus SET last_claim = ?, streak = ?
                    WHERE user_id = ?
                ''', (today, streak, user_id))
            else:
                # Первый раз
                streak = 1
                cursor.execute('''
                    INSERT INTO daily_bonus (user_id, last_claim, streak)
                    VALUES (?, ?, ?)
                ''', (user_id, today, streak))
            
            # Рассчитываем бонус
            base_bonus = 100
            bonus = base_bonus + (streak - 1) * 50  # +50 за каждый день стрика
            
            # Начисляем бонус
            cursor.execute('''
                UPDATE users SET balance = balance + ? WHERE user_id = ?
            ''', (bonus, user_id))
            
            # Записываем транзакцию
            cursor.execute('''
                INSERT INTO transactions (user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, bonus, "daily_bonus", f"Ежедневный бонус (стрик: {streak} дней)"))
            
            conn.commit()
            
            return {
                "bonus": bonus,
                "streak": streak
            }

# Создаем глобальный экземпляр базы данных
db = Database()