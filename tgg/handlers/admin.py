# handlers/admin.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS, RUB_TO_COINS, MIN_DEPOSIT
from database import db
from utils import format_number
import datetime
import asyncio

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


def get_admin_http_payment_keyboard(donation_id: str):
    """Клавиатура для управления конкретным HTTP платежом"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить", callback_data=f"admin_confirm_da_{donation_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отклонить", callback_data=f"admin_reject_da_{donation_id}"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(
            text="👤 Привязать к пользователю",
            callback_data=f"admin_bind_da_{donation_id}",
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад", callback_data="admin_pending_http_payments"
        ),
        width=1,
    )

    return builder.as_markup()


def get_admin_withdraw_payment_keyboard(request_id: int):
    """Клавиатура для управления заявкой на вывод"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить", callback_data=f"admin_confirm_withdraw_{request_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отклонить", callback_data=f"admin_reject_withdraw_{request_id}"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_pending_withdraws"),
        width=1,
    )

    return builder.as_markup()


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


@router.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    """Обработка введенного ID пользователя"""
    try:
        target_id = int(message.text.strip())
        data = await state.get_data()
        action = data.get("action")

        user = db.get_user(target_id)

        if action in ["give", "take", "check"]:
            if not user:
                await message.answer(
                    f"❌ Пользователь с ID {target_id} не найден!",
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
                await state.clear()
                return

            await state.update_data(target_id=target_id)
            action_text = "начисления" if action == "give" else "списания"
            await message.answer(
                f"💰 Введите сумму для {action_text} (целое число):\n"
                f"Текущий баланс пользователя: {format_number(user['balance'])} монет",
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
            await state.set_state(AdminStates.waiting_for_amount)

        elif action in ["ban", "unban", "set_admin", "remove_admin"]:
            if not user:
                await message.answer(
                    f"❌ Пользователь с ID {target_id} не найден!",
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

    except ValueError:
        await message.answer(
            "❌ Введите корректный ID (число)!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
                ]
            ),
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
            else:
                await message.answer(
                    "❌ Ошибка при начислении баланса",
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
            else:
                await message.answer(
                    "❌ Ошибка при списании баланса (возможно недостаточно средств)",
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

        await state.clear()

    except ValueError:
        await message.answer(
            "❌ Введите число!",
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

    await state.clear()
    await callback.answer()


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


@router.callback_query(F.data == "admin_http_check_now")
async def admin_http_check_now(callback: types.CallbackQuery):
    """Ручная проверка донатов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.answer("🔄 Проверка запущена...", show_alert=False)

    # Импортируем здесь, чтобы избежать циклического импорта
    try:
        from donation_polling import donation_poller

        if donation_poller and donation_poller.http_client:
            donation_poller.http_client.check_new_donations()
            await callback.message.answer("✅ Проверка выполнена")
        else:
            await callback.message.answer("❌ Poller не инициализирован")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")


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

    # Простая статистика
    pending = len(db.get_withdraw_requests("pending"))
    completed = len(db.get_withdraw_requests("completed"))

    text = (
        f"📊 **Статистика выводов**\n\n"
        f"⏳ Ожидает: {pending}\n"
        f"✅ Завершено: {completed}\n"
        f"❌ Отклонено: {len(db.get_withdraw_requests('rejected'))}\n\n"
        f"Функция расширенной статистики в разработке"
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


@router.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    """Заглушка для неактивных кнопок"""
    await callback.answer()
