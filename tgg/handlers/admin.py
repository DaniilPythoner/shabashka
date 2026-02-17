# handlers/admin.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import datetime
import asyncio

from config import ADMIN_IDS, RUB_TO_COINS
from database import db
from utils import format_number, DICE_EMOJIS

# Импортируем функции для управления активными играми
from handlers.admin_game_control import (
    active_games,
    register_active_game,
    unregister_active_game,
    force_game_result,
    get_active_games_list_keyboard,
    get_user_game_control_keyboard,
    get_dice_value_keyboard,
)

router = Router()


# Состояния для FSM
class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_ban_reason = State()
    waiting_for_mailing_text = State()
    waiting_for_mailing_confirm = State()
    waiting_for_withdraw_id = State()
    waiting_for_donation_id = State()
    waiting_for_game_action = State()
    waiting_for_force_result = State()
    waiting_for_dice_value = State()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    # Проверяем по списку из config
    if user_id in ADMIN_IDS:
        return True

    # Проверяем по базе данных
    user = db.get_user(user_id)
    return user and user.get("is_admin", False)


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
        InlineKeyboardButton(
            text="💰 DonationAlerts", callback_data="admin_donation_menu"
        ),
        InlineKeyboardButton(
            text="💸 Заявки на вывод", callback_data="admin_withdraws_menu"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(
            text="🎮 Управление играми", callback_data="admin_game_control"
        ),
        width=1,
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


def get_admin_donation_keyboard():
    """Клавиатура управления DonationAlerts для админа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📋 Ожидающие платежи", callback_data="admin_pending_http_payments"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Проверить сейчас", callback_data="admin_http_check_now"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика платежей", callback_data="admin_http_stats"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"), width=1
    )

    return builder.as_markup()


def get_admin_withdraws_keyboard():
    """Клавиатура управления выводами для админа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📋 Ожидающие выводы", callback_data="admin_pending_withdraws"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика выводов", callback_data="admin_withdraw_stats"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"), width=1
    )

    return builder.as_markup()


def get_admin_game_control_keyboard():
    """Клавиатура управления играми"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🎮 Активные игры", callback_data="admin_active_games"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="👤 Поиск игры по ID", callback_data="admin_search_game"
        ),
        InlineKeyboardButton(
            text="📊 Статистика игр", callback_data="admin_games_stats"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Принудительный результат", callback_data="admin_force_result_menu"
        ),
        InlineKeyboardButton(
            text="⏭ Пропустить ожидание", callback_data="admin_skip_wait_menu"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"), width=1
    )

    return builder.as_markup()


def get_force_result_keyboard():
    """Клавиатура для выбора типа принудительного результата"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Выигрыш", callback_data="admin_force_win"),
        InlineKeyboardButton(text="❌ Проигрыш", callback_data="admin_force_lose"),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Ничья", callback_data="admin_force_draw"),
        InlineKeyboardButton(
            text="🎲 Установить значение", callback_data="admin_force_dice"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control"),
        width=1,
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
        InlineKeyboardButton(text="🔍 Поиск", callback_data="admin_users_search"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=2,
    )

    return builder.as_markup()


def get_back_keyboard(callback: str):
    """Вспомогательная клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=callback), width=1)
    return builder.as_markup()


# ============================================
# ОСНОВНЫЕ ОБРАБОТЧИКИ АДМИН-ПАНЕЛИ
# ============================================


@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Команда для открытия админ-панели"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора!")
        return

    await message.answer(
        "👋 **Добро пожаловать в админ-панель!**\n\n" "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_main_keyboard(),
    )


@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    """Открытие админ-панели"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "👋 **Админ-панель**\n\n" "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_main_keyboard(),
    )
    await callback.answer()


# ============================================
# СТАТИСТИКА
# ============================================


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    """Общая статистика бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    total_users = db.get_total_users_count()
    total_games = db.get_total_games_count()
    total_bets = db.get_total_bets_sum()
    total_wins = db.get_total_wins_sum()

    # Получаем топ игроков
    top_players = db.get_top_players(3)
    top_text = ""
    for player in top_players:
        name = player["first_name"] or player["username"] or f"ID {player['user_id']}"
        top_text += f"├ {name}: {format_number(player['balance'])} монет\n"

    stats_text = (
        f"📊 **Общая статистика**\n\n"
        f"👥 Всего пользователей: **{total_users}**\n"
        f"🎮 Всего игр: **{total_games}**\n"
        f"💰 Общая сумма ставок: **{format_number(total_bets)}**\n"
        f"💸 Общая сумма выигрышей: **{format_number(total_wins)}**\n"
        f"📈 Профит казино: **{format_number(total_bets - total_wins)}**\n\n"
        f"🏆 **Топ-3 игроков:**\n{top_text}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
        ]
    )

    await callback.message.edit_text(
        stats_text, parse_mode="Markdown", reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "admin_daily_stats")
async def admin_daily_stats(callback: types.CallbackQuery):
    """Ежедневная статистика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    stats = db.get_daily_stats()

    text = (
        f"📈 **Статистика за сегодня**\n\n"
        f"👥 Новых пользователей: **{stats['new_users']}**\n"
        f"🎮 Сыграно игр: **{stats['games_today']}**\n"
        f"💰 Сумма ставок: **{format_number(stats['bets_today'])}**\n"
        f"💸 Сумма выплат: **{format_number(stats['wins_today'])}**\n"
        f"📊 Профит: **{format_number(stats['profit_today'])}**"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


# ============================================
# УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ============================================


@router.callback_query(F.data == "admin_users_list")
async def admin_users_list(callback: types.CallbackQuery):
    """Список пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await show_users_page(callback.message, 0)
    await callback.answer()


async def show_users_page(message: types.Message, page: int):
    """Отображение страницы с пользователями"""
    users = db.get_all_users(limit=10, offset=page * 10)
    total_users = db.get_total_users_count()
    total_pages = (total_users + 9) // 10

    text = f"👥 **Список пользователей** (страница {page + 1}/{total_pages})\n\n"

    for i, user in enumerate(users, page * 10 + 1):
        name = user["first_name"] or user["username"] or f"ID {user['user_id']}"
        status = []
        if user["is_banned"]:
            status.append("🔴 Забанен")
        if user["is_admin"]:
            status.append("👑 Админ")
        status_text = f" ({', '.join(status)})" if status else ""

        text += f"**{i}.** {name}{status_text}\n"
        text += f"   ├ ID: `{user['user_id']}`\n"
        text += f"   ├ 💰 {format_number(user['balance'])} монет\n"
        text += f"   ├ 🎮 {user['total_games']} игр\n"
        text += f"   └ 📅 {user['registration_date'][:10]}\n\n"

    await message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_users_navigation_keyboard(page, total_pages),
    )


@router.callback_query(F.data.startswith("admin_users_page_"))
async def users_page_navigation(callback: types.CallbackQuery):
    """Навигация по страницам пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    page = int(callback.data.split("_")[3])
    await show_users_page(callback.message, page)
    await callback.answer()


@router.callback_query(F.data == "admin_users_search")
async def admin_users_search(callback: types.CallbackQuery, state: FSMContext):
    """Поиск пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "🔍 Введите ID пользователя для поиска:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_users_list"
                    )
                ]
            ]
        ),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="search")
    await callback.answer()


# ============================================
# УПРАВЛЕНИЕ БАЛАНСОМ
# ============================================


@router.callback_query(F.data == "admin_balance_menu")
async def admin_balance_menu(callback: types.CallbackQuery):
    """Меню управления балансом"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "💰 **Управление балансом**\n\n" "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_balance_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_give_balance")
async def admin_give_balance(callback: types.CallbackQuery, state: FSMContext):
    """Выдача баланса пользователю"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "💰 Введите ID пользователя для начисления баланса:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_balance_menu"
                    )
                ]
            ]
        ),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="give")
    await callback.answer()


@router.callback_query(F.data == "admin_take_balance")
async def admin_take_balance(callback: types.CallbackQuery, state: FSMContext):
    """Списание баланса у пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "💰 Введите ID пользователя для списания баланса:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_balance_menu"
                    )
                ]
            ]
        ),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="take")
    await callback.answer()


@router.callback_query(F.data == "admin_check_balance")
async def admin_check_balance(callback: types.CallbackQuery, state: FSMContext):
    """Проверка баланса пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "💰 Введите ID пользователя для проверки баланса:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_balance_menu"
                    )
                ]
            ]
        ),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="check")
    await callback.answer()


# ============================================
# УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (БАН/АДМИН)
# ============================================


@router.callback_query(F.data == "admin_users_menu")
async def admin_users_menu(callback: types.CallbackQuery):
    """Меню управления пользователями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "🔨 **Управление пользователями**\n\n" "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_users_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_ban_user")
async def admin_ban_user(callback: types.CallbackQuery, state: FSMContext):
    """Блокировка пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "🔨 Введите ID пользователя для блокировки:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_users_menu"
                    )
                ]
            ]
        ),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="ban")
    await callback.answer()


@router.callback_query(F.data == "admin_unban_user")
async def admin_unban_user(callback: types.CallbackQuery, state: FSMContext):
    """Разблокировка пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "✅ Введите ID пользователя для разблокировки:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_users_menu"
                    )
                ]
            ]
        ),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="unban")
    await callback.answer()


@router.callback_query(F.data == "admin_set_admin")
async def admin_set_admin(callback: types.CallbackQuery, state: FSMContext):
    """Назначение администратора"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "👑 Введите ID пользователя для назначения администратором:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_users_menu"
                    )
                ]
            ]
        ),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_admin")
    await callback.answer()


@router.callback_query(F.data == "admin_remove_admin")
async def admin_remove_admin(callback: types.CallbackQuery, state: FSMContext):
    """Снятие администратора"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 Введите ID пользователя для снятия администратора:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_users_menu"
                    )
                ]
            ]
        ),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="remove_admin")
    await callback.answer()


# ============================================
# ОБРАБОТКА ID ПОЛЬЗОВАТЕЛЯ
# ============================================


@router.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    """Обработка введенного ID пользователя"""
    try:
        target_id = int(message.text.strip())
        data = await state.get_data()
        action = data.get("action")

        user = db.get_user(target_id)

        # Для поиска пользователя
        if action == "search":
            if not user:
                await message.answer(
                    f"❌ Пользователь с ID {target_id} не найден!",
                    reply_markup=get_back_keyboard("admin_users_list"),
                )
                await state.clear()
                return

            stats = db.get_user_stats(target_id)

            text = (
                f"👤 **Информация о пользователе**\n\n"
                f"ID: `{target_id}`\n"
                f"Имя: {user['first_name'] or 'Не указано'}\n"
                f"Username: @{user['username'] or 'Не указан'}\n"
                f"💰 Баланс: {format_number(user['balance'])} монет\n"
                f"🎮 Игр: {user['total_games']}\n"
                f"✅ Побед: {user['total_wins']}\n"
                f"❌ Поражений: {user['total_losses']}\n"
                f"👑 Админ: {'Да' if user['is_admin'] else 'Нет'}\n"
                f"🔒 Забанен: {'Да' if user['is_banned'] else 'Нет'}\n"
                f"👥 Рефералов: {stats['referrals_count']}"
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💰 Управление балансом",
                            callback_data=f"admin_balance_user_{target_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🎮 Активные игры",
                            callback_data=f"admin_user_games_{target_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="admin_users_list"
                        )
                    ],
                ]
            )

            await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
            await state.clear()
            return

        # Для операций с балансом
        if action in ["give", "take", "check"]:
            if not user:
                await message.answer(
                    f"❌ Пользователь с ID {target_id} не найден!",
                    reply_markup=get_back_keyboard("admin_balance_menu"),
                )
                await state.clear()
                return

            if action == "check":
                await message.answer(
                    f"📊 **Информация о пользователе**\n\n"
                    f"ID: `{target_id}`\n"
                    f"Имя: {user['first_name'] or 'Не указано'}\n"
                    f"Username: @{user['username'] or 'Не указан'}\n"
                    f"💰 Баланс: {format_number(user['balance'])} монет\n"
                    f"👑 Админ: {'Да' if user['is_admin'] else 'Нет'}\n"
                    f"🔒 Забанен: {'Да' if user['is_banned'] else 'Нет'}",
                    parse_mode="Markdown",
                    reply_markup=get_back_keyboard("admin_balance_menu"),
                )
                await state.clear()
                return

            await state.update_data(target_id=target_id)
            action_text = "начисления" if action == "give" else "списания"
            await message.answer(
                f"💰 Введите сумму для {action_text} (целое число):\n"
                f"Текущий баланс пользователя: {format_number(user['balance'])} монет",
                reply_markup=get_back_keyboard("admin_balance_menu"),
            )
            await state.set_state(AdminStates.waiting_for_amount)

        # Для действий с пользователями (бан, админ)
        elif action in ["ban", "unban", "set_admin", "remove_admin"]:
            if not user:
                await message.answer(
                    f"❌ Пользователь с ID {target_id} не найден!",
                    reply_markup=get_back_keyboard("admin_users_menu"),
                )
                await state.clear()
                return

            action_names = {
                "ban": "заблокировать",
                "unban": "разблокировать",
                "set_admin": "назначить администратором",
                "remove_admin": "снять с администратора",
            }

            # Клавиатура подтверждения
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Подтвердить",
                            callback_data=f"confirm_{action}_{target_id}",
                        ),
                        InlineKeyboardButton(
                            text="❌ Отмена", callback_data="admin_users_menu"
                        ),
                    ]
                ]
            )

            await message.answer(
                f"❓ Вы действительно хотите {action_names[action]} пользователя\n"
                f"ID: `{target_id}`\n"
                f"Имя: {user['first_name'] or 'Не указано'}?",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            await state.update_data(target_id=target_id, action=action)
            await state.set_state(AdminStates.waiting_for_ban_reason)

        # Для управления играми
        elif action in [
            "game_detail",
            "force_win",
            "force_lose",
            "force_draw",
            "set_dice",
        ]:
            if target_id not in active_games:
                await message.answer(
                    f"❌ У пользователя {target_id} нет активных игр",
                    reply_markup=get_back_keyboard("admin_game_control"),
                )
                await state.clear()
                return

            game_data = active_games[target_id]

            if action == "game_detail":
                user = db.get_user(target_id)
                time_passed = datetime.now() - game_data["start_time"]
                minutes = int(time_passed.total_seconds() // 60)
                seconds = int(time_passed.total_seconds() % 60)

                game_type_names = {
                    "guess": "Угадай число",
                    "highlow": "Больше/Меньше 3",
                    "duel": "Дуэль с ботом",
                    "craps": "Крэпс",
                }

                text = (
                    f"👤 **Игрок:** {user['first_name'] or user['username'] or 'Неизвестно'}\n"
                    f"🆔 **ID:** `{target_id}`\n"
                    f"💰 **Баланс:** {format_number(user['balance'])} монет\n\n"
                    f"🎮 **Игра:** {game_type_names.get(game_data['game_type'], game_data['game_type'])}\n"
                    f"💵 **Ставка:** {game_data['bet']} монет\n"
                    f"⏱ **Длительность:** {minutes} мин {seconds} сек\n\n"
                    f"**Действия:**"
                )

                await message.answer(
                    text,
                    parse_mode="Markdown",
                    reply_markup=get_user_game_control_keyboard(target_id, game_data),
                )
                await state.clear()

            elif action in ["force_win", "force_lose", "force_draw"]:
                await state.update_data(target_id=target_id, game_action=action)
                await process_force_result(message, state)

            elif action == "set_dice":
                await state.update_data(target_id=target_id)
                await message.answer(
                    f"🎲 Выберите значение для игры:\n\n" f"Игрок: `{target_id}`",
                    parse_mode="Markdown",
                    reply_markup=get_dice_value_keyboard(target_id),
                )
                await state.set_state(AdminStates.waiting_for_dice_value)

    except ValueError:
        await message.answer(
            "❌ Введите корректный ID (число)!",
            reply_markup=get_back_keyboard("admin_panel"),
        )
        await state.clear()


@router.message(AdminStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    """Обработка суммы для начисления/списания"""
    try:
        amount = int(message.text)
        data = await state.get_data()
        target_id = data.get("target_id")
        action = data.get("action")

        user = db.get_user(target_id)

        if action == "give":
            if db.update_balance(
                target_id,
                amount,
                "admin",
                f"Начислено администратором {message.from_user.id}",
            ):
                new_balance = db.get_user(target_id)["balance"]
                await message.answer(
                    f"✅ Баланс пользователя {user['first_name'] or target_id} увеличен\n"
                    f"Сумма: +{amount} монет\n"
                    f"Новый баланс: {format_number(new_balance)} монет",
                    reply_markup=get_back_keyboard("admin_balance_menu"),
                )
            else:
                await message.answer(
                    "❌ Ошибка при начислении баланса",
                    reply_markup=get_back_keyboard("admin_balance_menu"),
                )

        elif action == "take":
            if db.update_balance(
                target_id,
                -amount,
                "admin",
                f"Списано администратором {message.from_user.id}",
            ):
                new_balance = db.get_user(target_id)["balance"]
                await message.answer(
                    f"✅ Баланс пользователя {user['first_name'] or target_id} уменьшен\n"
                    f"Сумма: -{amount} монет\n"
                    f"Новый баланс: {format_number(new_balance)} монет",
                    reply_markup=get_back_keyboard("admin_balance_menu"),
                )
            else:
                await message.answer(
                    "❌ Ошибка при списании баланса (возможно недостаточно средств)",
                    reply_markup=get_back_keyboard("admin_balance_menu"),
                )

        await state.clear()

    except ValueError:
        await message.answer(
            "❌ Введите число!", reply_markup=get_back_keyboard("admin_balance_menu")
        )


@router.callback_query(lambda c: c.data.startswith("confirm_"))
async def confirm_action(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение действия с пользователем"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    parts = callback.data.split("_")
    action = parts[1]
    target_id = int(parts[2])

    user = db.get_user(target_id)
    admin_id = callback.from_user.id

    result = False
    action_text = ""

    if action == "ban":
        result = db.ban_user(target_id)
        action_text = "заблокирован"
    elif action == "unban":
        result = db.unban_user(target_id)
        action_text = "разблокирован"
    elif action == "set_admin":
        result = db.set_admin(target_id)
        action_text = "назначен администратором"
    elif action == "remove_admin":
        result = db.remove_admin(target_id)
        action_text = "снят с администратора"

    if result:
        await callback.message.edit_text(
            f"✅ Пользователь {user['first_name'] or target_id} {action_text}",
            reply_markup=get_back_keyboard("admin_users_menu"),
        )

        # Уведомляем пользователя
        try:
            notify_text = {
                "ban": "⛔ Вы были заблокированы администратором.",
                "unban": "✅ Вы были разблокированы.",
                "set_admin": "👑 Вам назначены права администратора!",
                "remove_admin": "👤 У вас сняты права администратора.",
            }.get(action, "")

            await callback.bot.send_message(target_id, notify_text)
        except:
            pass
    else:
        await callback.message.edit_text(
            "❌ Ошибка при выполнении операции",
            reply_markup=get_back_keyboard("admin_users_menu"),
        )

    await state.clear()
    await callback.answer()


# ============================================
# УПРАВЛЕНИЕ DONATIONALERTS
# ============================================


@router.callback_query(F.data == "admin_donation_menu")
async def admin_donation_menu(callback: types.CallbackQuery):
    """Меню управления DonationAlerts"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "💰 **Управление DonationAlerts**\n\n" "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_donation_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_pending_http_payments")
async def admin_pending_http_payments(callback: types.CallbackQuery):
    """Список ожидающих платежей из HTTP"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    payments = db.get_pending_http_payments()

    if not payments:
        await callback.message.edit_text(
            "📭 Нет ожидающих платежей из DonationAlerts",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔄 Обновить",
                            callback_data="admin_pending_http_payments",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="admin_donation_menu"
                        )
                    ],
                ]
            ),
        )
        await callback.answer()
        return

    text = "📋 **Ожидающие платежи DonationAlerts**\n\n"

    for p in payments[:10]:
        text += f"🆔 ID: `{p['donation_id'][:8]}...`\n"
        text += f"👤 Отправитель: {p['username']}\n"
        text += f"💰 {p['amount']} руб. = {p['coins']} монет\n"
        text += f"💬 Сообщение: {p['message'][:30] or '—'}\n"
        text += f"📅 {p['created_at'][:16]}\n\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить", callback_data="admin_pending_http_payments"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="admin_donation_menu"
                )
            ],
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_http_stats")
async def admin_http_stats(callback: types.CallbackQuery):
    """Статистика платежей DonationAlerts"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    stats = db.get_http_payment_stats()

    text = (
        f"📊 **Статистика DonationAlerts**\n\n"
        f"💰 Всего пополнений: {stats['total_count']}\n"
        f"💵 Общая сумма: {stats['total_amount']} руб.\n"
        f"📈 Сегодня: {stats['today_amount']} руб.\n"
        f"⏳ Ожидает: {stats['pending_count']}\n\n"
        f"Курс обмена: 1 рубль = {RUB_TO_COINS} монет"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_donation_menu")]
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_http_check_now")
async def admin_http_check_now(callback: types.CallbackQuery):
    """Ручная проверка донатов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.answer("🔄 Проверка запущена...", show_alert=False)

    try:
        from donation_polling import donation_poller

        if donation_poller and donation_poller.http_client:
            donation_poller.http_client.check_new_donations()
            await callback.message.answer("✅ Проверка выполнена")
        else:
            await callback.message.answer("❌ Poller не инициализирован")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")


# ============================================
# УПРАВЛЕНИЕ ВЫВОДАМИ
# ============================================


@router.callback_query(F.data == "admin_withdraws_menu")
async def admin_withdraws_menu(callback: types.CallbackQuery):
    """Меню управления выводами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "💸 **Управление выводами**\n\n" "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_withdraws_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_pending_withdraws")
async def admin_pending_withdraws(callback: types.CallbackQuery):
    """Список ожидающих выводов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    withdraws = db.get_withdraw_requests("pending")

    if not withdraws:
        await callback.message.edit_text(
            "📭 Нет ожидающих заявок на вывод",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔄 Обновить", callback_data="admin_pending_withdraws"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="admin_withdraws_menu"
                        )
                    ],
                ]
            ),
        )
        await callback.answer()
        return

    text = "📋 **Ожидающие заявки на вывод**\n\n"

    for w in withdraws[:10]:
        user = db.get_user(w["user_id"])
        username = (
            f"@{user['username']}"
            if user and user["username"]
            else f"ID {w['user_id']}"
        )

        text += f"🆔 Заявка #{w['id']}\n"
        text += f"👤 {username}\n"
        text += f"💰 Сумма: {w['amount']} руб.\n"
        text += f"🎲 Монет: {w['coins']}\n"
        text += f"💳 Карта: {w['card_number'][:4]} **** {w['card_number'][-4:]}\n"
        text += f"🏦 Банк: {w['bank_name']}\n"
        text += f"📅 {w['created_at'][:16]}\n\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить", callback_data="admin_pending_withdraws"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="admin_withdraws_menu"
                )
            ],
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin_withdraw_stats")
async def admin_withdraw_stats(callback: types.CallbackQuery):
    """Статистика выводов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    pending = len(db.get_withdraw_requests("pending"))
    completed = len(db.get_withdraw_requests("completed"))
    rejected = len(db.get_withdraw_requests("rejected"))

    text = (
        f"📊 **Статистика выводов**\n\n"
        f"⏳ Ожидает: {pending}\n"
        f"✅ Завершено: {completed}\n"
        f"❌ Отклонено: {rejected}\n"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="admin_withdraws_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


# ============================================
# УПРАВЛЕНИЕ ИГРАМИ
# ============================================


@router.callback_query(F.data == "admin_game_control")
async def admin_game_control(callback: types.CallbackQuery):
    """Меню управления играми"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "🎮 **Управление играми**\n\n"
        "Здесь вы можете просматривать активные игры пользователей\n"
        "и вмешиваться в их результат в реальном времени.\n\n"
        f"**Активных игр:** {len(active_games)}",
        parse_mode="Markdown",
        reply_markup=get_admin_game_control_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_active_games")
async def admin_active_games(callback: types.CallbackQuery):
    """Список активных игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    if not active_games:
        await callback.message.edit_text(
            "📭 Нет активных игр в данный момент",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="admin_game_control"
                        )
                    ]
                ]
            ),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🎮 **Активные игры**\n\n" "Нажмите на игру для управления:",
        parse_mode="Markdown",
        reply_markup=get_active_games_list_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_game_detail_"))
async def admin_game_detail(callback: types.CallbackQuery):
    """Детальная информация об игре"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    user_id = int(callback.data.split("_")[3])

    if user_id not in active_games:
        await callback.message.edit_text(
            "❌ Игра больше не активна",
            reply_markup=get_back_keyboard("admin_active_games"),
        )
        await callback.answer()
        return

    game_data = active_games[user_id]
    user = db.get_user(user_id)

    time_passed = datetime.now() - game_data["start_time"]
    minutes = int(time_passed.total_seconds() // 60)
    seconds = int(time_passed.total_seconds() % 60)

    game_type_names = {
        "guess": "Угадай число",
        "highlow": "Больше/Меньше 3",
        "duel": "Дуэль с ботом",
        "craps": "Крэпс",
    }

    text = (
        f"👤 **Игрок:** {user['first_name'] or user['username'] or 'Неизвестно'}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"💰 **Баланс:** {format_number(user['balance'])} монет\n\n"
        f"🎮 **Игра:** {game_type_names.get(game_data['game_type'], game_data['game_type'])}\n"
        f"💵 **Ставка:** {game_data['bet']} монет\n"
        f"⏱ **Длительность:** {minutes} мин {seconds} сек\n\n"
        f"**Действия:**"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_user_game_control_keyboard(user_id, game_data),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_search_game")
async def admin_search_game(callback: types.CallbackQuery, state: FSMContext):
    """Поиск игры по ID пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 Введите ID пользователя для просмотра игры:",
        reply_markup=get_back_keyboard("admin_game_control"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="game_detail")
    await callback.answer()


@router.callback_query(F.data == "admin_force_result_menu")
async def admin_force_result_menu(callback: types.CallbackQuery, state: FSMContext):
    """Меню принудительного результата"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "🎲 **Принудительный результат**\n\n" "Выберите тип результата:",
        parse_mode="Markdown",
        reply_markup=get_force_result_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_force_win")
async def admin_force_win_menu(callback: types.CallbackQuery, state: FSMContext):
    """Принудительный выигрыш - запрос ID"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 Введите ID пользователя для принудительного выигрыша:",
        reply_markup=get_back_keyboard("admin_force_result_menu"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="force_win")
    await callback.answer()


@router.callback_query(F.data == "admin_force_lose")
async def admin_force_lose_menu(callback: types.CallbackQuery, state: FSMContext):
    """Принудительный проигрыш - запрос ID"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 Введите ID пользователя для принудительного проигрыша:",
        reply_markup=get_back_keyboard("admin_force_result_menu"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="force_lose")
    await callback.answer()


@router.callback_query(F.data == "admin_force_draw")
async def admin_force_draw_menu(callback: types.CallbackQuery, state: FSMContext):
    """Принудительная ничья - запрос ID"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 Введите ID пользователя для принудительной ничьи:",
        reply_markup=get_back_keyboard("admin_force_result_menu"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="force_draw")
    await callback.answer()


@router.callback_query(F.data == "admin_force_dice")
async def admin_force_dice_menu(callback: types.CallbackQuery, state: FSMContext):
    """Установка значения кости - запрос ID"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 Введите ID пользователя для установки значения кости:",
        reply_markup=get_back_keyboard("admin_force_result_menu"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_dice")
    await callback.answer()


async def process_force_result(message: types.Message, state: FSMContext):
    """Обработка принудительного результата"""
    data = await state.get_data()
    target_id = data.get("target_id")
    game_action = data.get("game_action")

    game_data = active_games[target_id]
    bet = game_data["bet"]

    multipliers = {"guess": 5, "highlow": 2, "duel": 2, "craps": 1.5}

    multiplier = multipliers.get(game_data["game_type"], 2)

    if game_action == "force_win":
        win_amount = int(bet * multiplier)
        result_data = {
            "win_amount": win_amount,
            "text": f"🎉 **АДМИНИСТРАТОР УСТАНОВИЛ ВЫИГРЫШ!**\n\n💰 Выигрыш: +{win_amount} монет\n🎲 Множитель: x{multiplier}",
        }
        action_text = "выигрыш"
    elif game_action == "force_lose":
        result_data = {
            "win_amount": 0,
            "text": f"❌ **АДМИНИСТРАТОР УСТАНОВИЛ ПРОИГРЫШ!**\n\n💸 Потеряно: {bet} монет",
        }
        action_text = "проигрыш"
    elif game_action == "force_draw":
        result_data = {
            "win_amount": bet,
            "text": f"🔄 **АДМИНИСТРАТОР УСТАНОВИЛ НИЧЬЮ!**\n\n💰 Ставка возвращена: +{bet} монет",
        }
        action_text = "ничью"
    else:
        await message.answer("❌ Неизвестное действие")
        await state.clear()
        return

    success, result_message = await force_game_result(
        message.bot, target_id, result_data
    )

    if success:
        await message.answer(
            f"✅ Принудительный {action_text} установлен для пользователя {target_id}",
            reply_markup=get_back_keyboard("admin_game_control"),
        )
    else:
        await message.answer(
            f"❌ Ошибка: {result_message}",
            reply_markup=get_back_keyboard("admin_game_control"),
        )

    await state.clear()


@router.callback_query(F.data.startswith("admin_win_"))
async def admin_win_callback(callback: types.CallbackQuery):
    """Быстрый выигрыш из списка игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    user_id = int(callback.data.split("_")[2])

    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return

    game_data = active_games[user_id]
    bet = game_data["bet"]

    multipliers = {"guess": 5, "highlow": 2, "duel": 2, "craps": 1.5}

    multiplier = multipliers.get(game_data["game_type"], 2)
    win_amount = int(bet * multiplier)

    result_data = {
        "win_amount": win_amount,
        "text": f"🎉 **АДМИНИСТРАТОР УСТАНОВИЛ ВЫИГРЫШ!**\n\n💰 Выигрыш: +{win_amount} монет\n🎲 Множитель: x{multiplier}",
    }

    success, message = await force_game_result(callback.bot, user_id, result_data)

    if success:
        await callback.answer("✅ Выигрыш установлен!", show_alert=True)
        # Обновляем список активных игр
        await admin_active_games(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)


@router.callback_query(F.data.startswith("admin_lose_"))
async def admin_lose_callback(callback: types.CallbackQuery):
    """Быстрый проигрыш из списка игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    user_id = int(callback.data.split("_")[2])

    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return

    game_data = active_games[user_id]
    bet = game_data["bet"]

    result_data = {
        "win_amount": 0,
        "text": f"❌ **АДМИНИСТРАТОР УСТАНОВИЛ ПРОИГРЫШ!**\n\n💸 Потеряно: {bet} монет",
    }

    success, message = await force_game_result(callback.bot, user_id, result_data)

    if success:
        await callback.answer("✅ Проигрыш установлен!", show_alert=True)
        await admin_active_games(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)


@router.callback_query(F.data.startswith("admin_draw_"))
async def admin_draw_callback(callback: types.CallbackQuery):
    """Быстрая ничья из списка игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    user_id = int(callback.data.split("_")[2])

    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return

    game_data = active_games[user_id]
    bet = game_data["bet"]

    result_data = {
        "win_amount": bet,
        "text": f"🔄 **АДМИНИСТРАТОР УСТАНОВИЛ НИЧЬЮ!**\n\n💰 Ставка возвращена: +{bet} монет",
    }

    success, message = await force_game_result(callback.bot, user_id, result_data)

    if success:
        await callback.answer("✅ Ничья установлена!", show_alert=True)
        await admin_active_games(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)


@router.callback_query(F.data.startswith("admin_set_dice_"))
async def admin_set_dice(callback: types.CallbackQuery):
    """Установка значения кости из списка игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    user_id = int(callback.data.split("_")[3])

    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        f"🎲 Выберите значение для игры:\n\n" f"Игрок: `{user_id}`",
        parse_mode="Markdown",
        reply_markup=get_dice_value_keyboard(user_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_set_value_"))
async def admin_set_value(callback: types.CallbackQuery):
    """Установка конкретного значения"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    parts = callback.data.split("_")
    user_id = int(parts[3])
    value = int(parts[4])

    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return

    game_data = active_games[user_id]
    bet = game_data["bet"]

    # Определяем результат на основе значения
    if game_data["game_type"] == "guess":
        # Для угадай числа результат не определен без знания загаданного числа
        # По умолчанию считаем, что пользователь не угадал
        win_amount = 0
        result_text = f"🎲 Выпало: {value} {DICE_EMOJIS[value-1]}\n\n❌ Администратор установил проигрыш"

    elif game_data["game_type"] == "highlow":
        if value <= 3:
            win_amount = 0
            result_text = f"🎲 Выпало: {value} {DICE_EMOJIS[value-1]}\n\n❌ Администратор установил проигрыш"
        elif value <= 5:
            win_amount = bet
            result_text = f"🎲 Выпало: {value} {DICE_EMOJIS[value-1]}\n\n🔄 Администратор установил ничью"
        else:
            win_amount = bet * 2
            result_text = f"🎲 Выпало: {value} {DICE_EMOJIS[value-1]}\n\n🎉 Администратор установил выигрыш! +{win_amount} монет"

    else:
        await callback.answer(
            "❌ Этот тип игры не поддерживает одиночное значение", show_alert=True
        )
        return

    result_data = {"win_amount": win_amount, "text": result_text}

    success, message = await force_game_result(callback.bot, user_id, result_data)

    if success:
        await callback.answer("✅ Результат установлен!", show_alert=True)
        await admin_active_games(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)


@router.callback_query(F.data.startswith("admin_end_game_"))
async def admin_end_game(callback: types.CallbackQuery):
    """Принудительное завершение игры (возврат ставки)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    user_id = int(callback.data.split("_")[3])

    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return

    game_data = active_games[user_id]
    bet = game_data["bet"]

    result_data = {
        "win_amount": bet,
        "text": f"🔄 **ИГРА ПРЕРВАНА АДМИНИСТРАТОРОМ**\n\n💰 Ставка возвращена: +{bet} монет",
    }

    success, message = await force_game_result(callback.bot, user_id, result_data)

    if success:
        await callback.answer("✅ Игра завершена, ставка возвращена", show_alert=True)
        await admin_active_games(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)


@router.callback_query(F.data == "admin_skip_wait_menu")
async def admin_skip_wait_menu(callback: types.CallbackQuery, state: FSMContext):
    """Меню пропуска ожидания"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "⏭ **Пропуск ожидания**\n\n"
        "Введите ID пользователя, чье ожидание нужно пропустить:",
        reply_markup=get_back_keyboard("admin_game_control"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="skip_wait")
    await callback.answer()


@router.callback_query(F.data == "admin_games_stats")
async def admin_games_stats(callback: types.CallbackQuery):
    """Статистика игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    total_games = db.get_total_games_count()

    # Получаем статистику по типам игр
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT game_type, COUNT(*) as count, SUM(bet_amount) as total_bets, SUM(win_amount) as total_wins
            FROM games
            GROUP BY game_type
        """
        )
        stats = cursor.fetchall()

    text = f"📊 **Статистика игр**\n\n"
    text += f"🎮 Всего игр: {total_games}\n\n"

    game_names = {
        "guess": "Угадай число",
        "highlow": "Больше/Меньше",
        "duel": "Дуэль",
        "craps": "Крэпс",
    }

    for stat in stats:
        game_type, count, total_bets, total_wins = stat
        name = game_names.get(game_type, game_type)
        profit = (total_bets or 0) - (total_wins or 0)

        text += f"**{name}:**\n"
        text += f"  ├ Игр: {count}\n"
        text += f"  ├ Ставок: {format_number(total_bets or 0)}\n"
        text += f"  ├ Выплат: {format_number(total_wins or 0)}\n"
        text += f"  └ Профит: {format_number(profit)}\n\n"

    text += f"\n🎲 **Активных игр сейчас:** {len(active_games)}"

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("admin_game_control"),
    )
    await callback.answer()


# ============================================
# РАССЫЛКА
# ============================================


@router.callback_query(F.data == "admin_mailing")
async def admin_mailing(callback: types.CallbackQuery, state: FSMContext):
    """Рассылка сообщений"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "📢 Введите текст для рассылки всем пользователям:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
            ]
        ),
    )
    await state.set_state(AdminStates.waiting_for_mailing_text)
    await callback.answer()


@router.message(AdminStates.waiting_for_mailing_text)
async def process_mailing_text(message: types.Message, state: FSMContext):
    """Обработка текста рассылки"""
    await state.update_data(
        mailing_text=message.text,
        mailing_parse_mode=(
            "Markdown" if "**" in message.text or "*" in message.text else None
        ),
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить", callback_data="confirm_mailing"
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel"),
            ]
        ]
    )

    await message.answer(
        f"📢 **Предпросмотр рассылки:**\n\n{message.text}\n\n"
        f"Отправить это сообщение всем пользователям?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    await state.set_state(AdminStates.waiting_for_mailing_confirm)


@router.callback_query(
    AdminStates.waiting_for_mailing_confirm, F.data == "confirm_mailing"
)
async def confirm_mailing(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение рассылки"""
    data = await state.get_data()
    text = data.get("mailing_text")
    parse_mode = data.get("mailing_parse_mode")

    await callback.message.edit_text(
        "📢 Рассылка начата... Это может занять некоторое время.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
            ]
        ),
    )

    # Получаем всех пользователей
    all_users = []
    offset = 0
    while True:
        users = db.get_all_users(limit=100, offset=offset)
        if not users:
            break
        all_users.extend(users)
        offset += 100

    sent = 0
    failed = 0

    for user in all_users:
        if user["is_banned"]:
            continue

        try:
            await callback.bot.send_message(
                user["user_id"], text, parse_mode=parse_mode
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await callback.message.edit_text(
        f"📢 **Рассылка завершена**\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
            ]
        ),
    )

    await state.clear()
    await callback.answer()


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ОБРАБОТЧИКИ
# ============================================


@router.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    """Заглушка для неактивных кнопок"""
    await callback.answer()
