# handlers/admin.py
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio

from config import ADMIN_IDS
from database import db
from keyboards import (
    get_admin_keyboard,
    get_users_navigation_keyboard,
    get_back_keyboard,
    get_confirmation_keyboard,
)
from utils import format_number

router = Router()


class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_reason = State()
    waiting_for_mailing_text = State()
    waiting_for_mailing_confirm = State()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    user = db.get_user(user_id)
    return user and (user.get("is_admin") or user_id in ADMIN_IDS)


@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    """Открытие админ-панели"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.message.edit_text(
        "⚙️ **Админ-панель**\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    """Общая статистика бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
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

    await callback.message.edit_text(
        stats_text, parse_mode="Markdown", reply_markup=get_back_keyboard("admin_panel")
    )
    await callback.answer()


@router.callback_query(F.data == "admin_daily_stats")
async def admin_daily_stats(callback: types.CallbackQuery):
    """Ежедневная статистика"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
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

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard("admin_panel")
    )
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery, state: FSMContext):
    """Список пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return

    users = db.get_all_users(limit=10, offset=0)
    total_users = db.get_total_users_count()
    total_pages = (total_users + 9) // 10

    await show_users_page(callback.message, users, 0, total_pages)
    await callback.answer()


async def show_users_page(
    message: types.Message, users: list, page: int, total_pages: int
):
    """Отображение страницы с пользователями"""
    text = f"👥 **Список пользователей** (страница {page + 1}/{total_pages})\n\n"

    for i, user in enumerate(users, page * 10 + 1):
        name = user["first_name"] or user["username"] or f"ID {user['user_id']}"
        status = "🔴" if user["is_banned"] else "🟢"

        text += f"{status} **{i}.** {name}\n"
        text += f"   ├ ID: `{user['user_id']}`\n"
        text += f"   ├ 💰 {format_number(user['balance'])} монет\n"
        text += f"   ├ 🎮 {user['total_games']} игр\n"
        text += f"   └ 📅 {user['registration_date'][:10]}\n\n"

    await message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_users_navigation_keyboard(page, total_pages),
    )


@router.callback_query(F.data.startswith("users_page_"))
async def users_page_navigation(callback: types.CallbackQuery):
    """Навигация по страницам пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return

    page = int(callback.data.split("_")[2])
    users = db.get_all_users(limit=10, offset=page * 10)
    total_users = db.get_total_users_count()
    total_pages = (total_users + 9) // 10

    await show_users_page(callback.message, users, page, total_pages)
    await callback.answer()


@router.callback_query(F.data == "admin_give_balance")
async def admin_give_balance(callback: types.CallbackQuery, state: FSMContext):
    """Выдача баланса пользователю"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return

    await callback.message.edit_text(
        "💰 Введите ID пользователя:", reply_markup=get_back_keyboard("admin_panel")
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="give_balance")
    await callback.answer()


@router.callback_query(F.data == "admin_ban")
async def admin_ban(callback: types.CallbackQuery, state: FSMContext):
    """Блокировка пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return

    await callback.message.edit_text(
        "🔨 Введите ID пользователя для блокировки:",
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="ban")
    await callback.answer()


@router.callback_query(F.data == "admin_unban")
async def admin_unban(callback: types.CallbackQuery, state: FSMContext):
    """Разблокировка пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return

    await callback.message.edit_text(
        "✅ Введите ID пользователя для разблокировки:",
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="unban")
    await callback.answer()


@router.callback_query(F.data == "admin_set_admin")
async def admin_set_admin(callback: types.CallbackQuery, state: FSMContext):
    """Назначение администратора"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return

    await callback.message.edit_text(
        "👑 Введите ID пользователя для назначения администратором:",
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_admin")
    await callback.answer()


@router.callback_query(F.data == "admin_remove_admin")
async def admin_remove_admin(callback: types.CallbackQuery, state: FSMContext):
    """Снятие администратора"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return

    await callback.message.edit_text(
        "👤 Введите ID пользователя для снятия администратора:",
        reply_markup=get_back_keyboard("admin_panel"),
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="remove_admin")
    await callback.answer()


@router.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    """Обработка введенного ID пользователя"""
    try:
        target_id = int(message.text)
        data = await state.get_data()
        action = data.get("action")

        user = db.get_user(target_id)
        if not user:
            await message.answer(
                f"❌ Пользователь с ID {target_id} не найден",
                reply_markup=get_back_keyboard("admin_panel"),
            )
            await state.clear()
            return

        if action == "give_balance":
            await state.update_data(target_id=target_id)
            await message.answer(
                f"💰 Пользователь: {user['first_name'] or target_id}\n"
                f"Текущий баланс: {format_number(user['balance'])} монет\n\n"
                f"Введите сумму для начисления (или отрицательную для списания):",
                reply_markup=get_back_keyboard("admin_panel"),
            )
            await state.set_state(AdminStates.waiting_for_amount)

        elif action == "ban":
            if user["is_banned"]:
                await message.answer(
                    f"❌ Пользователь уже заблокирован",
                    reply_markup=get_back_keyboard("admin_panel"),
                )
                await state.clear()
                return

            await state.update_data(target_id=target_id)
            await message.answer(
                f"🔨 Заблокировать пользователя {user['first_name'] or target_id}?\n"
                f"ID: `{target_id}`",
                parse_mode="Markdown",
                reply_markup=get_confirmation_keyboard("ban"),
            )
            await state.set_state(AdminStates.waiting_for_reason)

        elif action == "unban":
            if not user["is_banned"]:
                await message.answer(
                    f"❌ Пользователь не заблокирован",
                    reply_markup=get_back_keyboard("admin_panel"),
                )
                await state.clear()
                return

            await state.update_data(target_id=target_id)
            await message.answer(
                f"✅ Разблокировать пользователя {user['first_name'] or target_id}?\n"
                f"ID: `{target_id}`",
                parse_mode="Markdown",
                reply_markup=get_confirmation_keyboard("unban"),
            )
            await state.set_state(AdminStates.waiting_for_reason)

        elif action == "set_admin":
            if user["is_admin"]:
                await message.answer(
                    f"❌ Пользователь уже является администратором",
                    reply_markup=get_back_keyboard("admin_panel"),
                )
                await state.clear()
                return

            await state.update_data(target_id=target_id)
            await message.answer(
                f"👑 Назначить администратором пользователя {user['first_name'] or target_id}?\n"
                f"ID: `{target_id}`",
                parse_mode="Markdown",
                reply_markup=get_confirmation_keyboard("set_admin"),
            )
            await state.set_state(AdminStates.waiting_for_reason)

        elif action == "remove_admin":
            if not user["is_admin"]:
                await message.answer(
                    f"❌ Пользователь не является администратором",
                    reply_markup=get_back_keyboard("admin_panel"),
                )
                await state.clear()
                return

            await state.update_data(target_id=target_id)
            await message.answer(
                f"👤 Снять администратора с пользователя {user['first_name'] or target_id}?\n"
                f"ID: `{target_id}`",
                parse_mode="Markdown",
                reply_markup=get_confirmation_keyboard("remove_admin"),
            )
            await state.set_state(AdminStates.waiting_for_reason)

    except ValueError:
        await message.answer(
            "❌ Введите корректный ID (число)",
            reply_markup=get_back_keyboard("admin_panel"),
        )
        await state.clear()


@router.message(AdminStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    """Обработка суммы для начисления"""
    try:
        amount = int(message.text)
        data = await state.get_data()
        target_id = data.get("target_id")

        user = db.get_user(target_id)

        if db.update_balance(
            target_id, amount, "admin", f"Админ: {message.from_user.id}"
        ):
            new_balance = db.get_user(target_id)["balance"]
            await message.answer(
                f"✅ Баланс пользователя {user['first_name'] or target_id} изменен\n"
                f"Сумма: {amount:+} монет\n"
                f"Новый баланс: {format_number(new_balance)} монет",
                reply_markup=get_back_keyboard("admin_panel"),
            )
        else:
            await message.answer(
                "❌ Ошибка при изменении баланса",
                reply_markup=get_back_keyboard("admin_panel"),
            )

        await state.clear()

    except ValueError:
        await message.answer(
            "❌ Введите число", reply_markup=get_back_keyboard("admin_panel")
        )


@router.callback_query(AdminStates.waiting_for_reason, F.data.startswith("confirm_"))
async def confirm_action(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение действия"""
    action = callback.data.split("_")[1]
    data = await state.get_data()
    target_id = data.get("target_id")

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
            reply_markup=get_back_keyboard("admin_panel"),
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при выполнении операции",
            reply_markup=get_back_keyboard("admin_panel"),
        )

    await state.clear()
    await callback.answer()


@router.callback_query(AdminStates.waiting_for_reason, F.data.startswith("cancel_"))
async def cancel_action(callback: types.CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await callback.message.edit_text(
        "❌ Операция отменена", reply_markup=get_back_keyboard("admin_panel")
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "admin_mailing")
async def admin_mailing(callback: types.CallbackQuery, state: FSMContext):
    """Рассылка сообщений"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен")
        return

    await callback.message.edit_text(
        "📤 Введите текст для рассылки:", reply_markup=get_back_keyboard("admin_panel")
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

    await message.answer(
        f"📤 **Предпросмотр рассылки:**\n\n{message.text}\n\n"
        f"Отправить это сообщение всем пользователям?",
        parse_mode="Markdown",
        reply_markup=get_confirmation_keyboard("mailing"),
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
        "📤 Рассылка начата...", reply_markup=get_back_keyboard("admin_panel")
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
        except Exception:
            failed += 1

        # Небольшая задержка, чтобы избежать флуда
        await asyncio.sleep(0.05)

    await callback.message.edit_text(
        f"📤 **Рассылка завершена**\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("admin_panel"),
    )

    await state.clear()
    await callback.answer()


@router.callback_query(
    AdminStates.waiting_for_mailing_confirm, F.data == "cancel_mailing"
)
async def cancel_mailing(callback: types.CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    await callback.message.edit_text(
        "❌ Рассылка отменена", reply_markup=get_back_keyboard("admin_panel")
    )
    await state.clear()
    await callback.answer()
