# config.py
BOT_TOKEN = "8420838811:AAHj_D7EJ1uxk9SfPgSHmqsUGVDMUUpBiKg"  # Замените на свой токен
ADMIN_IDS = [1906799313]  # ID администраторов (замените на свои)

# Настройки игр
START_BALANCE = 1000
MIN_BET = 10
MAX_BET = 10000
REFERRAL_BONUS = 100  # Бонус за реферала
REFERRAL_BONUS_FRIEND = 50  # Бонус другу за регистрацию по рефералке

# Коэффициенты выигрыша
MULTIPLIERS = {
    "guess": 5,  # Угадай число x5
    "highlow": 2,  # Больше/меньше x2
    "duel": 2,  # Дуэль x2
    "craps": 1.5,  # Крэпс x1.5
}

# Настройки базы данных
DATABASE_NAME = "dice_bot.db"
