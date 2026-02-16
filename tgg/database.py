# database.py
import sqlite3
import datetime
import random
import string
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
            
            # Таблица банковских платежей (пополнение)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bank_deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    coins_amount INTEGER,
                    payment_code TEXT UNIQUE,
                    receipt_photo_id TEXT,
                    status TEXT DEFAULT 'pending',
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    admin_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица заявок на вывод на карту
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS withdraw_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    coins_amount INTEGER,
                    card_number TEXT,
                    card_holder TEXT,
                    bank_name TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    admin_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            
            # Таблица для генерации уникальных кодов платежей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payment_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE,
                    user_id INTEGER,
                    amount INTEGER,
                    is_used INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
    # === БАНКОВСКИЕ ПЛАТЕЖИ ===
    
    def generate_payment_code(self) -> str:
        """Генерация уникального кода платежа"""
        while True:
            # Формат: XX-XXXX-XX (буквы и цифры)
            code = f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=2))}-" \
                   f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-" \
                   f"{''.join(random.choices(string.ascii_uppercase + string.digits, k=2))}"
            
            # Проверяем уникальность
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM payment_codes WHERE code = ?", (code,))
                if not cursor.fetchone():
                    return code

    def create_bank_deposit(self, user_id: int, amount: int) -> Dict:
        """Создание заявки на пополнение через банк"""
        from config import RUB_TO_COINS, PAYMENT_EXPIRY_HOURS
        
        coins = amount * RUB_TO_COINS
        payment_code = self.generate_payment_code()
        expires_at = (datetime.datetime.now() + datetime.timedelta(hours=PAYMENT_EXPIRY_HOURS)).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bank_deposits (user_id, amount, coins_amount, payment_code, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, amount, coins, payment_code, expires_at))
            
            deposit_id = cursor.lastrowid
            
            # Сохраняем код платежа
            cursor.execute('''
                INSERT INTO payment_codes (code, user_id, amount)
                VALUES (?, ?, ?)
            ''', (payment_code, user_id, amount))
            
            conn.commit()
            
            return {
                "id": deposit_id,
                "code": payment_code,
                "amount": amount,
                "coins": coins,
                "expires_at": expires_at
            }

    def get_bank_deposit(self, deposit_id: int) -> Optional[Dict]:
        """Получение информации о заявке на пополнение"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, amount, coins_amount, payment_code, receipt_photo_id,
                       status, expires_at, created_at, completed_at, admin_id
                FROM bank_deposits WHERE id = ?
            ''', (deposit_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "amount": row[2],
                    "coins": row[3],
                    "code": row[4],
                    "receipt_photo": row[5],
                    "status": row[6],
                    "expires_at": row[7],
                    "created_at": row[8],
                    "completed_at": row[9],
                    "admin_id": row[10]
                }
            return None

    def get_bank_deposit_by_code(self, code: str) -> Optional[Dict]:
        """Получение заявки по коду платежа"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, amount, coins_amount, payment_code, receipt_photo_id,
                       status, expires_at, created_at, completed_at, admin_id
                FROM bank_deposits WHERE payment_code = ?
            ''', (code,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "amount": row[2],
                    "coins": row[3],
                    "code": row[4],
                    "receipt_photo": row[5],
                    "status": row[6],
                    "expires_at": row[7],
                    "created_at": row[8],
                    "completed_at": row[9],
                    "admin_id": row[10]
                }
            return None

    def update_deposit_receipt(self, deposit_id: int, photo_id: str):
        """Обновление фото чека для заявки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bank_deposits SET receipt_photo_id = ? WHERE id = ?
            ''', (photo_id, deposit_id))
            conn.commit()

    def confirm_deposit(self, deposit_id: int, admin_id: int) -> bool:
        """Подтверждение пополнения администратором"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем информацию о депозите
            cursor.execute('''
                SELECT user_id, coins_amount, status FROM bank_deposits WHERE id = ?
            ''', (deposit_id,))
            row = cursor.fetchone()
            
            if not row or row[2] != 'pending':
                return False
            
            user_id, coins, _ = row
            
            # Начисляем монеты пользователю
            cursor.execute('''
                UPDATE users SET balance = balance + ? WHERE user_id = ?
            ''', (coins, user_id))
            
            # Обновляем статус депозита
            cursor.execute('''
                UPDATE bank_deposits 
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP, admin_id = ?
                WHERE id = ?
            ''', (admin_id, deposit_id))
            
            # Записываем транзакцию
            cursor.execute('''
                INSERT INTO transactions (user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, coins, "bank_deposit", f"Пополнение через банк #{deposit_id}"))
            
            conn.commit()
            return True

    def reject_deposit(self, deposit_id: int, admin_id: int) -> bool:
        """Отклонение пополнения"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bank_deposits 
                SET status = 'rejected', completed_at = CURRENT_TIMESTAMP, admin_id = ?
                WHERE id = ? AND status = 'pending'
            ''', (admin_id, deposit_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_pending_deposits(self) -> List[Dict]:
        """Получение всех ожидающих пополнений"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, amount, coins_amount, payment_code, created_at, expires_at
                FROM bank_deposits 
                WHERE status = 'pending'
                ORDER BY created_at ASC
            ''')
            
            rows = cursor.fetchall()
            deposits = []
            for row in rows:
                deposits.append({
                    "id": row[0],
                    "user_id": row[1],
                    "amount": row[2],
                    "coins": row[3],
                    "code": row[4],
                    "created_at": row[5],
                    "expires_at": row[6]
                })
            return deposits

    def create_withdraw_request(self, user_id: int, amount: int, card_number: str, card_holder: str, bank_name: str) -> Optional[int]:
        """Создание заявки на вывод на карту"""
        from config import RUB_TO_COINS
        
        coins_needed = amount * RUB_TO_COINS
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем баланс
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance = cursor.fetchone()
            
            if not balance or balance[0] < coins_needed:
                return None
            
            # Создаем заявку
            cursor.execute('''
                INSERT INTO withdraw_requests (user_id, amount, coins_amount, card_number, card_holder, bank_name)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, amount, coins_needed, card_number, card_holder, bank_name))
            
            request_id = cursor.lastrowid
            
            # Списываем монеты
            cursor.execute('''
                UPDATE users SET balance = balance - ? WHERE user_id = ?
            ''', (coins_needed, user_id))
            
            # Записываем транзакцию
            cursor.execute('''
                INSERT INTO transactions (user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, -coins_needed, "withdraw_request", f"Заявка на вывод #{request_id}"))
            
            conn.commit()
            return request_id

    def get_withdraw_requests(self, status: str = 'pending') -> List[Dict]:
        """Получение заявок на вывод"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, amount, coins_amount, card_number, card_holder, bank_name, created_at
                FROM withdraw_requests
                WHERE status = ?
                ORDER BY created_at ASC
            ''', (status,))
            
            rows = cursor.fetchall()
            requests = []
            for row in rows:
                requests.append({
                    "id": row[0],
                    "user_id": row[1],
                    "amount": row[2],
                    "coins": row[3],
                    "card_number": row[4],
                    "card_holder": row[5],
                    "bank_name": row[6],
                    "created_at": row[7]
                })
            return requests

    def get_user_withdraw_requests(self, user_id: int) -> List[Dict]:
        """Получение заявок на вывод пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, amount, coins_amount, card_number, card_holder, bank_name, status, created_at, processed_at
                FROM withdraw_requests
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 10
            ''', (user_id,))
            
            rows = cursor.fetchall()
            requests = []
            for row in rows:
                requests.append({
                    "id": row[0],
                    "amount": row[1],
                    "coins": row[2],
                    "card_number": row[3],
                    "card_holder": row[4],
                    "bank_name": row[5],
                    "status": row[6],
                    "created_at": row[7],
                    "processed_at": row[8]
                })
            return requests

    def confirm_withdraw(self, request_id: int, admin_id: int) -> bool:
        """Подтверждение вывода администратором"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE withdraw_requests 
                SET status = 'completed', processed_at = CURRENT_TIMESTAMP, admin_id = ?
                WHERE id = ? AND status = 'pending'
            ''', (admin_id, request_id))
            conn.commit()
            return cursor.rowcount > 0

    def reject_withdraw(self, request_id: int, admin_id: int) -> bool:
        """Отклонение вывода с возвратом средств"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем информацию о заявке
            cursor.execute('''
                SELECT user_id, coins_amount FROM withdraw_requests WHERE id = ? AND status = 'pending'
            ''', (request_id,))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            user_id, coins = row
            
            # Возвращаем монеты пользователю
            cursor.execute('''
                UPDATE users SET balance = balance + ? WHERE user_id = ?
            ''', (coins, user_id))
            
            # Обновляем статус заявки
            cursor.execute('''
                UPDATE withdraw_requests 
                SET status = 'rejected', processed_at = CURRENT_TIMESTAMP, admin_id = ?
                WHERE id = ?
            ''', (admin_id, request_id))
            
            # Записываем транзакцию
            cursor.execute('''
                INSERT INTO transactions (user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            ''', (user_id, coins, "withdraw_refund", f"Возврат по заявке #{request_id}"))
            
            conn.commit()
            return True

    def get_user_payment_history(self, user_id: int, limit: int = 10) -> Dict:
        """Получение истории платежей пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # История пополнений
            cursor.execute('''
                SELECT id, amount, coins_amount, payment_code, status, created_at, completed_at
                FROM bank_deposits
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            deposits = cursor.fetchall()
            
            # История выводов
            cursor.execute('''
                SELECT id, amount, coins_amount, card_number, status, created_at, processed_at
                FROM withdraw_requests
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            withdraws = cursor.fetchall()
            
            return {
                "deposits": [
                    {
                        "id": d[0],
                        "amount": d[1],
                        "coins": d[2],
                        "code": d[3],
                        "status": d[4],
                        "created": d[5],
                        "completed": d[6]
                    } for d in deposits
                ],
                "withdraws": [
                    {
                        "id": w[0],
                        "amount": w[1],
                        "coins": w[2],
                        "card": w[3][-4:] if w[3] else "****",  # Показываем только последние 4 цифры
                        "status": w[4],
                        "created": w[5],
                        "processed": w[6]
                    } for w in withdraws
                ]
            }
    
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