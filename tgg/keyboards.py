# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_keyboard(user_id: int = None, is_admin: bool = False):
    """Главная клавиатура"""
    builder = InlineKeyboardBuilder()

    # Основные игры
    builder.row(
        InlineKeyboardButton(text="🎲 Кость", callback_data="roll_dice"),
        InlineKeyboardButton(text="🎲🎲 Две кости", callback_data="roll_two_dice"),
        width=2,
    )

    # Игры на деньги
    builder.row(
        InlineKeyboardButton(text="🎮 Игры на деньги", callback_data="games_menu"),
        width=1,
    )

    # Профиль и статистика
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="user_stats"),
        width=2,
    )

    # Реферальная система
    builder.row(
        InlineKeyboardButton(text="👥 Рефералы", callback_data="referrals"),
        InlineKeyboardButton(text="🎁 Бонус", callback_data="daily_bonus"),
        width=2,
    )

    # Топ игроков
    builder.row(
        InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top_players"),
        width=1,
    )

    # Админ-панель (только для админов)
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="⚙️ Админ-панель", callback_data="admin_panel"),
            width=1,
        )

    return builder.as_markup()


def get_games_keyboard():
    """Клавиатура выбора игр"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🎲 Угадай число (x5)", callback_data="game_guess"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="🎯 Больше/Меньше 3 (x2)", callback_data="game_highlow"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🎰 Дуэль с ботом (x2)", callback_data="game_duel"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🎲🎲 Крэпс (x1.5)", callback_data="game_craps"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"), width=1
    )

    return builder.as_markup()


def get_bet_keyboard(min_bet: int = 10, max_bet: int = 10000):
    """Клавиатура выбора ставки"""
    builder = InlineKeyboardBuilder()

    bet_options = [10, 50, 100, 500, 1000, 5000]

    # Фильтруем опции по мин/макс
    bet_options = [x for x in bet_options if min_bet <= x <= max_bet]

    # Добавляем кнопки ставок
    buttons = []
    for bet in bet_options:
        buttons.append(
            InlineKeyboardButton(text=f"💰 {bet}", callback_data=f"bet_{bet}")
        )

    # Распределяем по рядам (по 3 в ряд)
    for i in range(0, len(buttons), 3):
        builder.row(*buttons[i : i + 3])

    # Кнопка своей ставки и отмены
    builder.row(
        InlineKeyboardButton(text="✏️ Своя ставка", callback_data="custom_bet"), width=1
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_bet"), width=1
    )

    return builder.as_markup()


def get_admin_keyboard():
    """Клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📊 Общая статистика", callback_data="admin_stats"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="👥 Список пользователей", callback_data="admin_users"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="💰 Выдать баланс", callback_data="admin_give_balance"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔨 Забанить", callback_data="admin_ban"),
        InlineKeyboardButton(text="✅ Разбанить", callback_data="admin_unban"),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(
            text="👑 Назначить админа", callback_data="admin_set_admin"
        ),
        InlineKeyboardButton(
            text="👤 Снять админа", callback_data="admin_remove_admin"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(
            text="📈 Ежедневная статистика", callback_data="admin_daily_stats"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="📤 Рассылка", callback_data="admin_mailing"), width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"), width=1
    )

    return builder.as_markup()


def get_users_navigation_keyboard(page: int, total_pages: int):
    """Клавиатура навигации по списку пользователей"""
    builder = InlineKeyboardBuilder()

    nav_buttons = []

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"users_page_{page-1}")
        )

    nav_buttons.append(
        InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop")
    )

    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"users_page_{page+1}")
        )

    builder.row(*nav_buttons, width=3)
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"), width=1
    )

    return builder.as_markup()


def get_back_keyboard(callback: str = "back_to_main"):
    """Клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=callback), width=1)
    return builder.as_markup()


def get_confirmation_keyboard(action: str):
    """Клавиатура подтверждения"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_{action}"),
        width=2,
    )
    return builder.as_markup()
