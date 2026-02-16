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

    # Кошелек и топ
    builder.row(
        InlineKeyboardButton(text="💳 Кошелек", callback_data="wallet_menu"),
        InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top_players"),
        width=2,
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


def get_wallet_keyboard():
    """Клавиатура для кошелька"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🏦 Банковские операции", callback_data="bank_menu"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 История операций", callback_data="payment_history"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"), width=1
    )

    return builder.as_markup()


def get_bank_menu_keyboard():
    """Клавиатура для банковских операций"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="💰 Пополнить через банк", callback_data="bank_deposit"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="💳 Вывести на карту", callback_data="bank_withdraw"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 История операций", callback_data="payment_history"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="wallet_menu"), width=1
    )

    return builder.as_markup()


def get_deposit_amount_keyboard():
    """Клавиатура выбора суммы пополнения"""
    builder = InlineKeyboardBuilder()

    amounts = [500, 1000, 2000, 5000, 10000, 20000]

    for amount in amounts:
        coins = amount * 10
        builder.row(
            InlineKeyboardButton(
                text=f"💰 {amount} руб. = {coins} монет",
                callback_data=f"deposit_amount_{amount}",
            ),
            width=1,
        )

    builder.row(
        InlineKeyboardButton(text="✏️ Другая сумма", callback_data="deposit_custom"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="bank_deposit"), width=1
    )

    return builder.as_markup()


def get_withdraw_amount_keyboard(max_amount: int):
    """Клавиатура выбора суммы вывода"""
    builder = InlineKeyboardBuilder()

    amounts = [1000, 2000, 5000, 10000, 20000, 50000]
    valid_amounts = [a for a in amounts if a <= max_amount]

    for amount in valid_amounts:
        fee = amount * 3 // 100
        receive = amount - fee
        builder.row(
            InlineKeyboardButton(
                text=f"💸 {amount} руб. (получите {receive} руб.)",
                callback_data=f"withdraw_amount_{amount}",
            ),
            width=1,
        )

    builder.row(
        InlineKeyboardButton(text="✏️ Другая сумма", callback_data="withdraw_custom"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="bank_withdraw"), width=1
    )

    return builder.as_markup()


def get_deposit_confirmation_keyboard(deposit_id: int):
    """Клавиатура подтверждения оплаты"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Я оплатил", callback_data=f"confirm_deposit_{deposit_id}"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="bank_deposit"), width=1
    )

    return builder.as_markup()


def get_payment_status_keyboard(deposit_id: int):
    """Клавиатура для проверки статуса платежа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔄 Проверить статус", callback_data=f"check_deposit_{deposit_id}"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="bank_menu"), width=1
    )

    return builder.as_markup()


def get_withdraw_confirmation_keyboard():
    """Клавиатура подтверждения вывода"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить", callback_data="confirm_withdraw_final"
        ),
        InlineKeyboardButton(text="❌ Отмена", callback_data="bank_withdraw"),
        width=2,
    )

    return builder.as_markup()


def get_payment_history_keyboard():
    """Клавиатура для истории платежей"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📥 Пополнения", callback_data="history_deposits"),
        InlineKeyboardButton(text="📤 Выводы", callback_data="history_withdraws"),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="bank_menu"), width=1
    )

    return builder.as_markup()


def get_admin_main_keyboard():
    """Главная клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📊 Общая статистика", callback_data="admin_stats"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="👥 Список пользователей", callback_data="admin_users_list"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="💰 Управление балансом", callback_data="admin_balance_menu"
        ),
        InlineKeyboardButton(
            text="🔨 Управление пользователями", callback_data="admin_users_menu"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(text="🏦 Платежи", callback_data="admin_payments_menu"),
        InlineKeyboardButton(
            text="💸 Заявки на вывод", callback_data="admin_withdraws_menu"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_mailing"),
        InlineKeyboardButton(
            text="📈 Ежедневная статистика", callback_data="admin_daily_stats"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Выйти", callback_data="back_to_main"), width=1
    )

    return builder.as_markup()


def get_admin_balance_keyboard():
    """Клавиатура управления балансом для админа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="➕ Начислить", callback_data="admin_give_balance"),
        InlineKeyboardButton(text="➖ Списать", callback_data="admin_take_balance"),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Проверить баланс", callback_data="admin_check_balance"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"), width=1
    )

    return builder.as_markup()


def get_admin_users_keyboard():
    """Клавиатура управления пользователями для админа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔨 Забанить", callback_data="admin_ban_user"),
        InlineKeyboardButton(text="✅ Разбанить", callback_data="admin_unban_user"),
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
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"), width=1
    )

    return builder.as_markup()


def get_admin_payments_keyboard():
    """Клавиатура управления платежами для админа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📋 Ожидающие пополнения", callback_data="admin_pending_deposits"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Ожидающие выводы", callback_data="admin_pending_withdraws"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика платежей", callback_data="admin_payment_stats"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"), width=1
    )

    return builder.as_markup()


def get_users_navigation_keyboard(page: int, total_pages: int):
    """Клавиатура навигации по списку пользователей"""
    builder = InlineKeyboardBuilder()

    nav_buttons = []

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️", callback_data=f"admin_users_page_{page-1}")
        )

    nav_buttons.append(
        InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop")
    )

    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="▶️", callback_data=f"admin_users_page_{page+1}")
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


def get_yes_no_keyboard(callback_prefix: str):
    """Универсальная клавиатура да/нет"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"{callback_prefix}_yes"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"{callback_prefix}_no"),
        width=2,
    )
    return builder.as_markup()


def get_cancel_keyboard(callback: str = "back_to_main"):
    """Клавиатура с кнопкой отмены"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=callback), width=1)
    return builder.as_markup()
