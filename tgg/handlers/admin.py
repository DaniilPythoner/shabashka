# handlers/admin.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import datetime
import asyncio

from config import ADMIN_IDS, RUB_TO_COINS, MIN_BANK_DEPOSIT
from database import db
from utils import format_number, DICE_EMOJIS

# Импортируем функции для управления активными играми
from handlers.admin_game_control import (
    active_games, get_active_games_list_keyboard,
    get_user_game_control_keyboard, get_dice_value_keyboard
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

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    if user_id in ADMIN_IDS:
        return True
    user = db.get_user(user_id)
    return user and user.get("is_admin", False)

def get_admin_main_keyboard():
    """Главная клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📊 Общая статистика", callback_data="admin_stats"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_users_list"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="💰 Управление балансом", callback_data="admin_balance_menu"),
        InlineKeyboardButton(text="🔨 Управление пользователями", callback_data="admin_users_menu"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="💰 Банковские платежи", callback_data="admin_bank_menu"),
        InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="admin_withdraws_menu"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🎮 Управление играми", callback_data="admin_game_control"),
        InlineKeyboardButton(text="⚡ Управление удачей", callback_data="admin_luck_menu"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🎚️ Управление уровнями", callback_data="admin_levels_menu"),
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_mailing"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📈 Ежедневная статистика", callback_data="admin_daily_stats"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Выйти", callback_data="back_to_main"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_balance_keyboard():
    """Клавиатура управления балансом для админа"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="➕ Начислить", callback_data="admin_give_balance"),
        InlineKeyboardButton(text="➖ Списать", callback_data="admin_take_balance"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📊 Проверить баланс", callback_data="admin_check_balance"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_users_keyboard():
    """Клавиатура управления пользователями для админа"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔨 Забанить", callback_data="admin_ban_user"),
        InlineKeyboardButton(text="✅ Разбанить", callback_data="admin_unban_user"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="👑 Назначить админа", callback_data="admin_set_admin"),
        InlineKeyboardButton(text="👤 Снять админа", callback_data="admin_remove_admin"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_bank_keyboard():
    """Клавиатура управления банковскими платежами для админа"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📋 Ожидающие платежи", callback_data="admin_pending_bank"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика платежей", callback_data="admin_bank_stats"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_withdraws_keyboard():
    """Клавиатура управления выводами для админа"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📋 Ожидающие выводы", callback_data="admin_pending_withdraws"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика выводов", callback_data="admin_withdraw_stats"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_game_control_keyboard():
    """Клавиатура управления играми"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🎮 Активные игры", callback_data="admin_active_games"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="👤 Поиск игры по ID", callback_data="admin_search_game"),
        InlineKeyboardButton(text="📊 Статистика игр", callback_data="admin_games_stats"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_luck_keyboard():
    """Клавиатура управления удачей для админа"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="👁 Просмотреть удачу", callback_data="admin_luck_view"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="⬆️ Увеличить удачу", callback_data="admin_luck_increase"),
        InlineKeyboardButton(text="⬇️ Уменьшить удачу", callback_data="admin_luck_decrease"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="⚡ Установить значение", callback_data="admin_luck_set"),
        InlineKeyboardButton(text="🔄 Сбросить удачу", callback_data="admin_luck_reset"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📊 Топ по удаче", callback_data="admin_luck_top"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_levels_menu_keyboard():
    """Клавиатура управления уровнями для админа"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📊 Статистика уровней", callback_data="admin_levels_stats"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="👥 Топ по уровням", callback_data="admin_levels_top"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="⬆️ Повысить уровень", callback_data="admin_levels_upgrade"),
        InlineKeyboardButton(text="⬇️ Понизить уровень", callback_data="admin_levels_downgrade"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Сбросить уровень", callback_data="admin_levels_reset"),
        InlineKeyboardButton(text="🔍 Проверить уровень", callback_data="admin_levels_check"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="💰 Изменить потраченное", callback_data="admin_levels_spent"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=1
    )
    
    return builder.as_markup()

def get_users_navigation_keyboard(page: int, total_pages: int):
    """Клавиатура навигации по списку пользователей"""
    builder = InlineKeyboardBuilder()
    
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_users_page_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_users_page_{page+1}"))
    
    builder.row(*nav_buttons, width=3)
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск", callback_data="admin_users_search"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=2
    )
    
    return builder.as_markup()

def get_back_keyboard(callback: str):
    """Клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=callback),
        width=1
    )
    return builder.as_markup()

# ============================================
# ОСНОВНЫЕ ОБРАБОТЧИКИ
# ============================================

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Команда для открытия админ-панели"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора!")
        return
    
    await message.answer(
        "👋 **Добро пожаловать в админ-панель!**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_main_keyboard()
    )

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    """Открытие админ-панели"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👋 **Админ-панель**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_main_keyboard()
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
        name = player['first_name'] or player['username'] or f"ID {player['user_id']}"
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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="Markdown",
        reply_markup=keyboard
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
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
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
        name = user['first_name'] or user['username'] or f"ID {user['user_id']}"
        status = []
        if user['is_banned']:
            status.append("🔴 Забанен")
        if user['is_admin']:
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
        reply_markup=get_users_navigation_keyboard(page, total_pages)
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
    """Поиск пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔍 Введите ID пользователя для поиска:",
        reply_markup=get_back_keyboard("admin_users_list")
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
        "💰 **Управление балансом**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_balance_keyboard()
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
        reply_markup=get_back_keyboard("admin_balance_menu")
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
        reply_markup=get_back_keyboard("admin_balance_menu")
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
        reply_markup=get_back_keyboard("admin_balance_menu")
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
        "🔨 **Управление пользователями**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_users_keyboard()
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
        reply_markup=get_back_keyboard("admin_users_menu")
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
        reply_markup=get_back_keyboard("admin_users_menu")
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
        reply_markup=get_back_keyboard("admin_users_menu")
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
        reply_markup=get_back_keyboard("admin_users_menu")
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
        
        if action == "search":
            if not user:
                await message.answer(
                    f"❌ Пользователь с ID {target_id} не найден!",
                    reply_markup=get_back_keyboard("admin_users_list")
                )
                await state.clear()
                return
            
            stats = db.get_user_stats(target_id)
            user_level = db.get_user_level(target_id)
            custom_luck = db.get_user_custom_luck(target_id)
            
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
                f"🎚️ Уровень: {user_level['level_name']}\n"
                f"⚡ Модификатор удачи: x{custom_luck:.2f}\n"
                f"👥 Рефералов: {stats['referrals_count']}"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Управление балансом", callback_data=f"admin_balance_user_{target_id}")],
                [InlineKeyboardButton(text="🎮 Активные игры", callback_data=f"admin_user_games_{target_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users_list")]
            ])
            
            await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
            await state.clear()
            return
        
        if action in ["give", "take", "check"]:
            if not user:
                await message.answer(
                    f"❌ Пользователь с ID {target_id} не найден!",
                    reply_markup=get_back_keyboard("admin_balance_menu")
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
                    reply_markup=get_back_keyboard("admin_balance_menu")
                )
                await state.clear()
                return
            
            await state.update_data(target_id=target_id)
            action_text = "начисления" if action == "give" else "списания"
            await message.answer(
                f"💰 Введите сумму для {action_text} (целое число):\n"
                f"Текущий баланс пользователя: {format_number(user['balance'])} монет",
                reply_markup=get_back_keyboard("admin_balance_menu")
            )
            await state.set_state(AdminStates.waiting_for_amount)
            
        elif action in ["ban", "unban", "set_admin", "remove_admin"]:
            if not user:
                await message.answer(
                    f"❌ Пользователь с ID {target_id} не найден!",
                    reply_markup=get_back_keyboard("admin_users_menu")
                )
                await state.clear()
                return
            
            action_names = {
                "ban": "заблокировать",
                "unban": "разблокировать",
                "set_admin": "назначить администратором",
                "remove_admin": "снять с администратора"
            }
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{action}_{target_id}"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="admin_users_menu")
                ]
            ])
            
            await message.answer(
                f"❓ Вы действительно хотите {action_names[action]} пользователя\n"
                f"ID: `{target_id}`\n"
                f"Имя: {user['first_name'] or 'Не указано'}?",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            await state.update_data(target_id=target_id, action=action)
            await state.set_state(AdminStates.waiting_for_ban_reason)
            
    except ValueError:
        await message.answer(
            "❌ Введите корректный ID (число)!",
            reply_markup=get_back_keyboard("admin_panel")
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
            if db.update_balance(target_id, amount, "admin", f"Начислено администратором {message.from_user.id}"):
                new_balance = db.get_user(target_id)['balance']
                await message.answer(
                    f"✅ Баланс пользователя {user['first_name'] or target_id} увеличен\n"
                    f"Сумма: +{amount} монет\n"
                    f"Новый баланс: {format_number(new_balance)} монет",
                    reply_markup=get_back_keyboard("admin_balance_menu")
                )
            else:
                await message.answer(
                    "❌ Ошибка при начислении баланса",
                    reply_markup=get_back_keyboard("admin_balance_menu")
                )
                
        elif action == "take":
            if db.update_balance(target_id, -amount, "admin", f"Списано администратором {message.from_user.id}"):
                new_balance = db.get_user(target_id)['balance']
                await message.answer(
                    f"✅ Баланс пользователя {user['first_name'] or target_id} уменьшен\n"
                    f"Сумма: -{amount} монет\n"
                    f"Новый баланс: {format_number(new_balance)} монет",
                    reply_markup=get_back_keyboard("admin_balance_menu")
                )
            else:
                await message.answer(
                    "❌ Ошибка при списании баланса (возможно недостаточно средств)",
                    reply_markup=get_back_keyboard("admin_balance_menu")
                )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Введите число!",
            reply_markup=get_back_keyboard("admin_balance_menu")
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
            reply_markup=get_back_keyboard("admin_users_menu")
        )
        
        try:
            notify_text = {
                "ban": "⛔ Вы были заблокированы администратором.",
                "unban": "✅ Вы были разблокированы.",
                "set_admin": "👑 Вам назначены права администратора!",
                "remove_admin": "👤 У вас сняты права администратора."
            }.get(action, "")
            
            await callback.bot.send_message(
                target_id,
                notify_text
            )
        except:
            pass
    else:
        await callback.message.edit_text(
            "❌ Ошибка при выполнении операции",
            reply_markup=get_back_keyboard("admin_users_menu")
        )
    
    await state.clear()
    await callback.answer()

# ============================================
# БАНКОВСКИЕ ПЛАТЕЖИ
# ============================================

@router.callback_query(F.data == "admin_bank_menu")
async def admin_bank_menu(callback: types.CallbackQuery):
    """Меню управления банковскими платежами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💰 **Управление банковскими платежами**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_bank_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_pending_bank")
async def admin_pending_bank(callback: types.CallbackQuery):
    """Список ожидающих банковских платежей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    deposits = db.get_pending_bank_deposits()
    
    if not deposits:
        await callback.message.edit_text(
            "📭 Нет ожидающих банковских пополнений",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_pending_bank")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_bank_menu")]
            ])
        )
        await callback.answer()
        return
    
    text = "📋 **Ожидающие банковские пополнения**\n\n"
    
    for d in deposits[:10]:
        user = db.get_user(d['user_id'])
        username = f"@{user['username']}" if user and user['username'] else f"ID {d['user_id']}"
        
        text += f"🆔 Заявка #{d['id']}\n"
        text += f"👤 {username}\n"
        text += f"💰 {d['amount']} руб. = {d['coins']} монет\n"
        text += f"🔢 Код: `{d['code']}`\n"
        text += f"📅 Создана: {d['created_at'][:16]}\n"
        text += f"⏰ Истекает: {d['expires_at'][:16]}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_pending_bank")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_bank_menu")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "admin_bank_stats")
async def admin_bank_stats(callback: types.CallbackQuery):
    """Статистика банковских платежей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    # Получаем статистику из БД
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*), SUM(amount) FROM bank_deposits WHERE status = 'completed'
        ''')
        completed = cursor.fetchone()
        completed_count = completed[0] or 0
        completed_sum = completed[1] or 0
        
        cursor.execute('''
            SELECT COUNT(*), SUM(amount) FROM bank_deposits WHERE status = 'pending'
        ''')
        pending = cursor.fetchone()
        pending_count = pending[0] or 0
        pending_sum = pending[1] or 0
        
        cursor.execute('''
            SELECT COUNT(*), SUM(amount) FROM bank_deposits WHERE status = 'rejected'
        ''')
        rejected = cursor.fetchone()
        rejected_count = rejected[0] or 0
        rejected_sum = rejected[1] or 0
    
    text = (
        f"📊 **Статистика банковских платежей**\n\n"
        f"✅ **Завершенные:**\n"
        f"  • Количество: {completed_count}\n"
        f"  • Сумма: {format_number(completed_sum)} руб.\n\n"
        f"⏳ **В обработке:**\n"
        f"  • Количество: {pending_count}\n"
        f"  • Сумма: {format_number(pending_sum)} руб.\n\n"
        f"❌ **Отклоненные:**\n"
        f"  • Количество: {rejected_count}\n"
        f"  • Сумма: {format_number(rejected_sum)} руб.\n\n"
        f"💰 **Общая сумма пополнений:** {format_number(completed_sum)} руб."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_bank_menu")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

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
        "💸 **Управление выводами**\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_withdraws_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_pending_withdraws")
async def admin_pending_withdraws(callback: types.CallbackQuery):
    """Список ожидающих выводов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    withdraws = db.get_withdraw_requests('pending')
    
    if not withdraws:
        await callback.message.edit_text(
            "📭 Нет ожидающих заявок на вывод",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_pending_withdraws")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_withdraws_menu")]
            ])
        )
        await callback.answer()
        return
    
    text = "📋 **Ожидающие заявки на вывод**\n\n"
    
    for w in withdraws[:10]:
        user = db.get_user(w['user_id'])
        username = f"@{user['username']}" if user and user['username'] else f"ID {w['user_id']}"
        
        text += f"🆔 Заявка #{w['id']}\n"
        text += f"👤 {username}\n"
        text += f"💰 Сумма: {w['amount']} руб.\n"
        text += f"🎲 Монет: {w['coins']}\n"
        text += f"💳 Карта: {w['card_number'][:4]} **** {w['card_number'][-4:]}\n"
        text += f"🏦 Банк: {w['bank_name']}\n"
        text += f"📅 {w['created_at'][:16]}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_pending_withdraws")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_withdraws_menu")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "admin_withdraw_stats")
async def admin_withdraw_stats(callback: types.CallbackQuery):
    """Статистика выводов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    pending = len(db.get_withdraw_requests('pending'))
    completed = len(db.get_withdraw_requests('completed'))
    rejected = len(db.get_withdraw_requests('rejected'))
    
    # Получаем суммы
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT SUM(amount) FROM withdraw_requests WHERE status = "completed"')
        completed_sum = cursor.fetchone()[0] or 0
        cursor.execute('SELECT SUM(amount) FROM withdraw_requests WHERE status = "pending"')
        pending_sum = cursor.fetchone()[0] or 0
    
    text = (
        f"📊 **Статистика выводов**\n\n"
        f"⏳ **В обработке:**\n"
        f"  • Количество: {pending}\n"
        f"  • Сумма: {format_number(pending_sum)} руб.\n\n"
        f"✅ **Завершено:**\n"
        f"  • Количество: {completed}\n"
        f"  • Сумма: {format_number(completed_sum)} руб.\n\n"
        f"❌ **Отклонено:** {rejected}\n\n"
        f"💰 **Всего выведено:** {format_number(completed_sum)} руб."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_withdraws_menu")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
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
        f"**Активных игр:** {len(active_games)}",
        parse_mode="Markdown",
        reply_markup=get_admin_game_control_keyboard()
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
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control")]
            ])
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🎮 **Активные игры**\n\n"
        "Нажмите на игру для управления:",
        parse_mode="Markdown",
        reply_markup=get_active_games_list_keyboard()
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="game_detail")
    await callback.answer()

@router.callback_query(F.data == "admin_games_stats")
async def admin_games_stats(callback: types.CallbackQuery):
    """Статистика игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    total_games = db.get_total_games_count()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT game_type, COUNT(*) as count, SUM(bet_amount) as total_bets, SUM(win_amount) as total_wins
            FROM games
            GROUP BY game_type
        ''')
        stats = cursor.fetchall()
    
    text = f"📊 **Статистика игр**\n\n"
    text += f"🎮 Всего игр: {total_games}\n\n"
    
    game_names = {
        "guess": "Угадай число",
        "highlow": "Больше/Меньше",
        "duel": "Дуэль",
        "craps": "Крэпс"
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
        reply_markup=get_back_keyboard("admin_game_control")
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
        ])
    )
    await state.set_state(AdminStates.waiting_for_mailing_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_mailing_text)
async def process_mailing_text(message: types.Message, state: FSMContext):
    """Обработка текста рассылки"""
    await state.update_data(mailing_text=message.text, 
                           mailing_parse_mode="Markdown" if "**" in message.text or "*" in message.text else None)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_mailing"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")
        ]
    ])
    
    await message.answer(
        f"📢 **Предпросмотр рассылки:**\n\n{message.text}\n\n"
        f"Отправить это сообщение всем пользователям?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await state.set_state(AdminStates.waiting_for_mailing_confirm)

@router.callback_query(AdminStates.waiting_for_mailing_confirm, F.data == "confirm_mailing")
async def confirm_mailing(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение рассылки"""
    data = await state.get_data()
    text = data.get("mailing_text")
    parse_mode = data.get("mailing_parse_mode")
    
    await callback.message.edit_text(
        "📢 Рассылка начата... Это может занять некоторое время.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
        ])
    )
    
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
        if user['is_banned']:
            continue
        
        try:
            await callback.bot.send_message(
                user['user_id'],
                text,
                parse_mode=parse_mode
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
        ])
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