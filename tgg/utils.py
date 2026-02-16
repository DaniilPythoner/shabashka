# utils.py
import random
import hashlib
from typing import Tuple, Dict

# Эмодзи для костей
DICE_EMOJIS = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]


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


def generate_referral_link(bot_username: str, user_id: int) -> str:
    """Генерация реферальной ссылки"""
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def parse_referrer_from_start(start_param: str) -> int | None:
    """Извлечение ID реферера из start-параметра"""
    if start_param and start_param.startswith("ref_"):
        try:
            return int(start_param.split("_")[1])
        except (ValueError, IndexError):
            return None
    return None


# Игровые функции
def play_guess_game(bet: int, guess: int) -> Tuple[int, str]:
    """Игра 'Угадай число'"""
    dice = roll_dice()
    win = dice == guess
    win_amount = bet * 5 if win else 0

    result_text = f"🎲 Вам выпало: {dice} {DICE_EMOJIS[dice-1]}\n"

    if win:
        result_text += f"🎉 Поздравляем! Вы угадали число!\n+{win_amount} монет"
    else:
        result_text += f"❌ К сожалению, вы не угадали.\n-{bet} монет"

    return win_amount, result_text


def play_highlow_game(bet: int) -> Tuple[int, str]:
    """Игра 'Больше/Меньше 3'"""
    dice = roll_dice()
    dice_emoji = DICE_EMOJIS[dice - 1]

    result_text = f"{dice_emoji} Вам выпало: {dice}\n\n"

    if dice <= 3:
        win_amount = 0
        result_text += f"❌ Вы проиграли {bet} монет!"
    elif dice <= 5:
        win_amount = bet
        result_text += f"🔄 Ничья! Ставка возвращена."
    else:  # dice == 6
        win_amount = bet * 2
        result_text += f"🎉 Вы выиграли {win_amount} монет!"

    return win_amount, result_text


def play_duel_game(bet: int) -> Tuple[int, str]:
    """Игра 'Дуэль с ботом'"""
    player_d1, player_d2, player_sum, p_emoji1, p_emoji2 = roll_two_dice()
    bot_d1, bot_d2, bot_sum, b_emoji1, b_emoji2 = roll_two_dice()

    result_text = f"**Ваши кости:** {p_emoji1} {p_emoji2} = {player_sum}\n"
    result_text += f"**Кости бота:** {b_emoji1} {b_emoji2} = {bot_sum}\n\n"

    if player_sum > bot_sum:
        win_amount = bet * 2
        result_text += f"🎉 **ПОБЕДА!** +{win_amount} монет"
    elif player_sum < bot_sum:
        win_amount = 0
        result_text += f"❌ **ПОРАЖЕНИЕ!** -{bet} монет"
    else:
        win_amount = bet
        result_text += f"🔄 **НИЧЬЯ!** Ставка возвращена"

    return win_amount, result_text


def play_craps_game(bet: int) -> Tuple[int, str]:
    """Игра 'Крэпс'"""
    d1, d2, total, emoji1, emoji2 = roll_two_dice()

    result_text = f"{emoji1} {emoji2} = {total}\n\n"

    # Правила крэпса (упрощенные)
    if total in [7, 11]:
        win_amount = int(bet * 1.5)
        result_text += f"🎉 **NATURAL!** Вы выиграли {win_amount} монет!"
    elif total in [2, 3, 12]:
        win_amount = 0
        result_text += f"❌ **CRAPS!** Вы проиграли {bet} монет!"
    else:
        # Точка установлена
        point = total
        result_text += f"📌 Точка установлена: {point}\n\n"

        # Бросаем пока не выпадет точка или 7
        while True:
            d1, d2, new_total, _, _ = roll_two_dice()
            result_text += f"Бросок: {new_total}\n"

            if new_total == point:
                win_amount = int(bet * 1.5)
                result_text += f"🎉 Вы выиграли {win_amount} монет!"
                break
            elif new_total == 7:
                win_amount = 0
                result_text += f"❌ Вы проиграли {bet} монет!"
                break

    return win_amount, result_text


# Словарь игр
GAMES = {
    "guess": {
        "name": "Угадай число",
        "func": play_guess_game,
        "multiplier": 5,
        "description": "Угадайте число от 1 до 6 и выиграйте x5",
    },
    "highlow": {
        "name": "Больше/Меньше 3",
        "func": play_highlow_game,
        "multiplier": 2,
        "description": "1-3 проигрыш, 4-5 возврат, 6 выигрыш x2",
    },
    "duel": {
        "name": "Дуэль с ботом",
        "func": play_duel_game,
        "multiplier": 2,
        "description": "Сразитесь с ботом - у кого больше сумма",
    },
    "craps": {
        "name": "Крэпс",
        "func": play_craps_game,
        "multiplier": 1.5,
        "description": "Классическая игра в кости x1.5",
    },
}


def get_game_info(game_type: str) -> Dict:
    """Получение информации об игре"""
    return GAMES.get(game_type, {})
