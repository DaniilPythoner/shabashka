# utils.py
import random
import hashlib
from typing import Tuple, Dict, Optional, List
import json
import time

# Эмодзи для костей
DICE_EMOJIS = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

# ============================================
# БАЗОВЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С КОСТЯМИ
# ============================================

def roll_dice(sides: int = 6) -> int:
    """Бросок кости"""
    return random.randint(1, sides)

def roll_dice_with_emoji() -> Tuple[int, str]:
    """Бросок кости с эмодзи"""
    value = roll_dice()
    return value, DICE_EMOJIS[value - 1]

def roll_two_dice() -> Tuple[int, int, int, str, str]:
    """Бросок двух костей"""
    d1 = roll_dice()
    d2 = roll_dice()
    return d1, d2, d1 + d2, DICE_EMOJIS[d1 - 1], DICE_EMOJIS[d2 - 1]

def format_number(num: int) -> str:
    """Форматирование числа с разделителями"""
    return f"{num:,}".replace(",", " ")

# ============================================
# ФУНКЦИИ ДЛЯ РЕФЕРАЛЬНОЙ СИСТЕМЫ
# ============================================

def generate_referral_link(bot_username: str, user_id: int) -> str:
    """Генерация реферальной ссылки"""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

def parse_referrer_from_start(start_param: str) -> Optional[int]:
    """Извлечение ID реферера из start-параметра"""
    if start_param and start_param.startswith("ref_"):
        try:
            return int(start_param.split("_")[1])
        except (ValueError, IndexError):
            return None
    return None

# ============================================
# ФУНКЦИИ ДЛЯ РАСЧЕТА УДАЧИ
# ============================================

def apply_luck_to_game(win_amount: int, luck_multiplier: float, game_type: str) -> int:
    """
    Применение множителя удачи к выигрышу
    Удача увеличивает шанс на получение дополнительного бонуса
    
    Параметры:
    - win_amount: базовый выигрыш
    - luck_multiplier: множитель удачи (от 1.0 до 1.5)
    - game_type: тип игры (для разной механики бонусов)
    
    Возвращает:
    - итоговый выигрыш с учетом бонуса удачи
    """
    
    # Если множитель не увеличивает удачу, возвращаем исходную сумму
    if luck_multiplier <= 1.0:
        return win_amount
    
    # Базовая логика: чем выше множитель, тем больше шанс получить бонус
    # Множитель 1.05 = 10% шанс на бонус
    # Множитель 1.50 = 100% шанс на бонус
    bonus_chance = (luck_multiplier - 1.0) * 2  # 1.05 -> 0.1, 1.5 -> 1.0
    
    # Генерируем случайное число для определения бонуса
    chance = random.random()
    
    # Разные типы игр могут иметь разные бонусы
    if chance < bonus_chance:
        # Определяем размер бонуса в зависимости от типа игры
        if game_type == "guess":
            # Для игры "Угадай число" бонус может быть больше
            bonus_percent = random.uniform(0.10, 0.30)
        elif game_type == "duel":
            # Для дуэли бонус средний
            bonus_percent = random.uniform(0.05, 0.20)
        elif game_type == "craps":
            # Для крэпса бонус может быть чаще, но меньше
            bonus_percent = random.uniform(0.03, 0.15)
        else:  # highlow и другие
            bonus_percent = random.uniform(0.05, 0.15)
        
        # Рассчитываем бонус
        bonus = int(win_amount * bonus_percent)
        
        # Добавляем бонус к выигрышу
        win_amount += bonus
    
    return win_amount

# ============================================
# ФУНКЦИИ ДЛЯ ИГР (С УЧЕТОМ УДАЧИ)
# ============================================

def play_guess_game(bet: int, guess: int, luck_multiplier: float = 1.0) -> Tuple[int, str]:
    """
    Игра 'Угадай число' с учетом удачи
    Возвращает: (выигрыш, текст результата)
    """
    dice = roll_dice()
    win = dice == guess
    
    if win:
        win_amount = bet * 5
        # Применяем удачу
        win_amount = apply_luck_to_game(win_amount, luck_multiplier, "guess")
        result_text = (
            f"🎲 Вам выпало: {dice} {DICE_EMOJIS[dice-1]}\n"
            f"✅ Вы угадали число!\n"
            f"🎉 Выигрыш: +{win_amount} монет"
        )
        if luck_multiplier > 1.0:
            bonus_info = _get_luck_bonus_info(win_amount, bet * 5, luck_multiplier)
            result_text += f"\n{bonus_info}"
    else:
        win_amount = 0
        result_text = (
            f"🎲 Вам выпало: {dice} {DICE_EMOJIS[dice-1]}\n"
            f"❌ Вы не угадали число.\n"
            f"💸 Проигрыш: -{bet} монет"
        )
    
    return win_amount, result_text

def play_highlow_game(bet: int, luck_multiplier: float = 1.0) -> Tuple[int, str]:
    """
    Игра 'Больше/Меньше 3' с учетом удачи
    Возвращает: (выигрыш, текст результата)
    """
    dice = roll_dice()
    dice_emoji = DICE_EMOJIS[dice - 1]
    
    if dice <= 3:
        win_amount = 0
        result_text = (
            f"{dice_emoji} Вам выпало: {dice}\n\n"
            f"❌ Проигрыш! 1-3 - проигрыш\n"
            f"💸 Потеряно: {bet} монет"
        )
    elif dice <= 5:
        win_amount = bet
        result_text = (
            f"{dice_emoji} Вам выпало: {dice}\n\n"
            f"🔄 Ничья! 4-5 - возврат ставки\n"
            f"💰 Ставка возвращена"
        )
    else:  # dice == 6
        win_amount = bet * 2
        # Применяем удачу
        win_amount = apply_luck_to_game(win_amount, luck_multiplier, "highlow")
        result_text = (
            f"{dice_emoji} Вам выпало: {dice}\n\n"
            f"🎉 Выигрыш! 6 - выигрыш x2\n"
            f"💰 Выигрыш: +{win_amount} монет"
        )
        if luck_multiplier > 1.0:
            bonus_info = _get_luck_bonus_info(win_amount, bet * 2, luck_multiplier)
            result_text += f"\n{bonus_info}"
    
    return win_amount, result_text

def play_duel_game(bet: int, luck_multiplier: float = 1.0) -> Tuple[int, str]:
    """
    Игра 'Дуэль с ботом' с учетом удачи
    Возвращает: (выигрыш, текст результата)
    """
    player_d1, player_d2, player_sum, p_emoji1, p_emoji2 = roll_two_dice()
    bot_d1, bot_d2, bot_sum, b_emoji1, b_emoji2 = roll_two_dice()
    
    result_text = (
        f"**Ваши кости:** {p_emoji1} {p_emoji2} = {player_sum}\n"
        f"**Кости бота:** {b_emoji1} {b_emoji2} = {bot_sum}\n\n"
    )
    
    if player_sum > bot_sum:
        win_amount = bet * 2
        # Применяем удачу
        win_amount = apply_luck_to_game(win_amount, luck_multiplier, "duel")
        result_text += f"🎉 **ПОБЕДА!**\n💰 Выигрыш: +{win_amount} монет"
        if luck_multiplier > 1.0:
            bonus_info = _get_luck_bonus_info(win_amount, bet * 2, luck_multiplier)
            result_text += f"\n{bonus_info}"
    elif player_sum < bot_sum:
        win_amount = 0
        result_text += f"❌ **ПОРАЖЕНИЕ!**\n💸 Потеряно: {bet} монет"
    else:
        win_amount = bet
        result_text += f"🔄 **НИЧЬЯ!**\n💰 Ставка возвращена"
    
    return win_amount, result_text

def play_craps_game(bet: int, luck_multiplier: float = 1.0) -> Tuple[int, str]:
    """
    Игра 'Крэпс' с учетом удачи
    Возвращает: (выигрыш, текст результата)
    """
    d1, d2, total, emoji1, emoji2 = roll_two_dice()
    
    result_text = f"{emoji1} {emoji2} = {total}\n\n"
    
    if total in [7, 11]:
        win_amount = int(bet * 1.5)
        # Применяем удачу
        win_amount = apply_luck_to_game(win_amount, luck_multiplier, "craps")
        result_text += f"🎉 **NATURAL!** Выигрыш x1.5\n💰 +{win_amount} монет"
        if luck_multiplier > 1.0:
            bonus_info = _get_luck_bonus_info(win_amount, int(bet * 1.5), luck_multiplier)
            result_text += f"\n{bonus_info}"
    elif total in [2, 3, 12]:
        win_amount = 0
        result_text += f"❌ **CRAPS!** Проигрыш\n💸 Потеряно: {bet} монет"
    else:
        # Точка установлена
        point = total
        result_text += f"📌 Точка установлена: {point}\n\n"
        
        # Бросаем пока не выпадет точка или 7
        roll_count = 0
        max_rolls = 10
        rolls_history = []
        
        while roll_count < max_rolls:
            d1, d2, new_total, new_emoji1, new_emoji2 = roll_two_dice()
            rolls_history.append(f"{new_emoji1}{new_emoji2}={new_total}")
            
            if new_total == point:
                win_amount = int(bet * 1.5)
                # Применяем удачу
                win_amount = apply_luck_to_game(win_amount, luck_multiplier, "craps")
                result_text += f"Броски: {' → '.join(rolls_history)}\n"
                result_text += f"🎉 Вы выиграли! +{win_amount} монет"
                if luck_multiplier > 1.0:
                    bonus_info = _get_luck_bonus_info(win_amount, int(bet * 1.5), luck_multiplier)
                    result_text += f"\n{bonus_info}"
                break
            elif new_total == 7:
                win_amount = 0
                result_text += f"Броски: {' → '.join(rolls_history)}\n"
                result_text += f"❌ Вы проиграли! -{bet} монет"
                break
            roll_count += 1
        else:
            win_amount = bet
            result_text += f"Броски: {' → '.join(rolls_history)}\n"
            result_text += f"🔄 Слишком много бросков. Ставка возвращена"
    
    return win_amount, result_text

def _get_luck_bonus_info(final_amount: int, base_amount: int, luck_multiplier: float) -> str:
    """Вспомогательная функция для получения информации о бонусе удачи"""
    bonus = final_amount - base_amount
    if bonus > 0:
        return f"✨ Бонус удачи: +{bonus} монет (x{luck_multiplier})"
    return ""

# ============================================
# ДОПОЛНИТЕЛЬНЫЕ ИГРОВЫЕ ФУНКЦИИ
# ============================================

def get_game_statistics(games_history: List[Dict]) -> Dict:
    """
    Получение статистики по играм из истории
    """
    stats = {
        "total_games": len(games_history),
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "total_bet": 0,
        "total_win": 0,
        "net_profit": 0,
        "best_win": 0,
        "worst_loss": 0,
        "games_by_type": {}
    }
    
    for game in games_history:
        bet = game.get('bet_amount', 0)
        win = game.get('win_amount', 0)
        result = game.get('result', '')
        game_type = game.get('game_type', 'unknown')
        
        stats['total_bet'] += bet
        stats['total_win'] += win
        
        if result == 'win':
            stats['wins'] += 1
            if win > stats['best_win']:
                stats['best_win'] = win
        elif result == 'loss':
            stats['losses'] += 1
            if bet > stats['worst_loss']:
                stats['worst_loss'] = bet
        elif result == 'draw':
            stats['draws'] += 1
        
        # Статистика по типам игр
        if game_type not in stats['games_by_type']:
            stats['games_by_type'][game_type] = {
                "count": 0,
                "wins": 0,
                "losses": 0,
                "total_bet": 0,
                "total_win": 0
            }
        
        stats['games_by_type'][game_type]['count'] += 1
        stats['games_by_type'][game_type]['total_bet'] += bet
        stats['games_by_type'][game_type]['total_win'] += win
        if result == 'win':
            stats['games_by_type'][game_type]['wins'] += 1
        elif result == 'loss':
            stats['games_by_type'][game_type]['losses'] += 1
    
    stats['net_profit'] = stats['total_win'] - stats['total_bet']
    
    return stats

def get_win_rate(wins: int, total_games: int) -> float:
    """Расчет процента побед"""
    if total_games == 0:
        return 0.0
    return (wins / total_games) * 100

# ============================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С УРОВНЯМИ
# ============================================

def get_level_progress(current_level: int, total_spent: int, next_level_price: Optional[int] = None) -> Dict:
    """
    Получение прогресса по уровню
    """
    if not next_level_price:
        return {
            "percentage": 100,
            "current": total_spent,
            "next": None,
            "remaining": 0,
            "is_max": True
        }
    
    # Рассчитываем прогресс до следующего уровня
    percentage = min(100, (total_spent / next_level_price) * 100)
    remaining = max(0, next_level_price - total_spent)
    
    return {
        "percentage": round(percentage, 1),
        "current": total_spent,
        "next": next_level_price,
        "remaining": remaining,
        "is_max": False
    }

def get_level_name_with_emoji(level_number: int, level_name: str) -> str:
    """
    Получение названия уровня с эмодзи
    """
    emoji_map = {
        1: "🥉",  # Бронзовый 3
        2: "🥉",  # Бронзовый 2
        3: "🥉",  # Бронзовый 1
        4: "🥈",  # Серебряный 3
        5: "🥈",  # Серебряный 2
        6: "🥈",  # Серебряный 1
        7: "🥇",  # Золотой 3
        8: "🥇",  # Золотой 2
        9: "🥇",  # Золотой 1
        10: "💎"  # Бриллиантовый
    }
    
    emoji = emoji_map.get(level_number, "🎚️")
    return f"{emoji} {level_name}"

def get_next_level_price(current_level: int) -> Optional[int]:
    """
    Получение цены следующего уровня
    """
    prices = {
        1: 2500,   # Бронзовый 3 -> Бронзовый 2
        2: 5000,   # Бронзовый 2 -> Бронзовый 1
        3: 10000,  # Бронзовый 1 -> Серебряный 3
        4: 20000,  # Серебряный 3 -> Серебряный 2
        5: 35000,  # Серебряный 2 -> Серебряный 1
        6: 50000,  # Серебряный 1 -> Золотой 3
        7: 75000,  # Золотой 3 -> Золотой 2
        8: 100000, # Золотой 2 -> Золотой 1
        9: 150000, # Золотой 1 -> Бриллиантовый
        10: None   # Максимальный уровень
    }
    
    return prices.get(current_level)

# ============================================
#
# РАЗЛИЧНЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def generate_random_string(length: int = 8) -> str:
    """Генерация случайной строки"""
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def format_time_ago(timestamp: str) -> str:
    """
    Форматирование времени в формате "X времени назад"
    """
    from datetime import datetime
    
    try:
        if 'T' in timestamp:
            # ISO format
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            # SQL format
            dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        
        now = datetime.now()
        delta = now - dt
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} г. назад"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} мес. назад"
        elif delta.days > 0:
            return f"{delta.days} дн. назад"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} ч. назад"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} мин. назад"
        else:
            return "только что"
    except:
        return timestamp

def format_duration(seconds: int) -> str:
    """
    Форматирование длительности в секундах
    """
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes} мин {secs} сек"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} ч {minutes} мин"

# ============================================
# СЛОВАРЬ ИГР
# ============================================

GAMES = {
    "guess": {
        "name": "Угадай число",
        "func": play_guess_game,
        "multiplier": 5,
        "description": "Угадайте число от 1 до 6 и выиграйте x5",
        "emoji": "🎲",
        "min_bet": 10,
        "max_bet": 10000
    },
    "highlow": {
        "name": "Больше/Меньше 3",
        "func": play_highlow_game,
        "multiplier": 2,
        "description": "1-3 проигрыш, 4-5 возврат, 6 выигрыш x2",
        "emoji": "🎯",
        "min_bet": 10,
        "max_bet": 10000
    },
    "duel": {
        "name": "Дуэль с ботом",
        "func": play_duel_game,
        "multiplier": 2,
        "description": "Сразитесь с ботом - у кого больше сумма",
        "emoji": "🎰",
        "min_bet": 10,
        "max_bet": 10000
    },
    "craps": {
        "name": "Крэпс",
        "func": play_craps_game,
        "multiplier": 1.5,
        "description": "Классическая игра в кости x1.5",
        "emoji": "🎲🎲",
        "min_bet": 10,
        "max_bet": 10000
    }
}

def get_game_info(game_type: str) -> Dict:
    """Получение информации об игре"""
    return GAMES.get(game_type, {})

def get_all_games_info() -> List[Dict]:
    """Получение информации обо всех играх"""
    return [
        {
            "id": game_id,
            **game_info
        }
        for game_id, game_info in GAMES.items()
    ]

# ============================================
# ТЕСТОВЫЕ ФУНКЦИИ
# ============================================

def test_luck_system(iterations: int = 1000):
    """
    Тестирование системы удачи
    """
    results = {}
    
    for level in range(1, 11):
        multiplier = 1.0 + (level - 1) * 0.05
        if level > 6:
            multiplier = 1.3 + (level - 7) * 0.05
        
        wins = []
        for _ in range(iterations):
            base_win = 100
            final_win = apply_luck_to_game(base_win, multiplier, "test")
            wins.append(final_win)
        
        avg_win = sum(wins) / len(wins)
        bonus_rate = (avg_win - base_win) / base_win * 100
        
        results[level] = {
            "multiplier": multiplier,
            "avg_win": avg_win,
            "bonus_rate": bonus_rate
        }
    
    return results

if __name__ == "__main__":
    # Тестирование при прямом запуске
    print("🎲 Тестирование системы удачи")
    print("=" * 50)
    
    results = test_luck_system(10000)
    for level, data in results.items():
        print(f"Уровень {level}: множитель x{data['multiplier']:.2f}, "
              f"средний выигрыш {data['avg_win']:.1f} "
              f"(+{data['bonus_rate']:.1f}%)")
    
    print("\n" + "=" * 50)
    print("✅ Тестирование завершено")