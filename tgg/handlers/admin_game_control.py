# handlers/admin_game_control.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import random
from datetime import datetime, timedelta

from config import ADMIN_IDS
from database import db
from utils import format_number, roll_dice, DICE_EMOJIS

router = Router()

# Хранилище активных игр пользователей
# Структура: {user_id: {"game_type": str, "bet": int, "start_time": datetime, "message_id": int, "chat_id": int}}
active_games = {}

# Состояния для FSM
class AdminGameControlStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_game_action = State()
    waiting_for_force_result = State()
    waiting_for_dice_value = State()

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS or (db.get_user(user_id) or {}).get("is_admin", False)

def get_admin_game_control_keyboard():
    """Клавиатура управления играми"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🎮 Активные игры", callback_data="admin_active_games"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="👁 Просмотр игры", callback_data="admin_view_game"),
        InlineKeyboardButton(text="🎲 Изменить результат", callback_data="admin_force_result"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить ожидание", callback_data="admin_skip_wait"),
        InlineKeyboardButton(text="🔄 Перезапустить игру", callback_data="admin_restart_game"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика игр", callback_data="admin_games_stats"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"),
        width=1
    )
    
    return builder.as_markup()

def get_user_game_control_keyboard(user_id: int, game_data: dict):
    """Клавиатура для управления конкретной игрой пользователя"""
    builder = InlineKeyboardBuilder()
    
    game_type_names = {
        "guess": "🎲 Угадай число",
        "highlow": "🎯 Больше/Меньше",
        "duel": "🎰 Дуэль",
        "craps": "🎲🎲 Крэпс"
    }
    
    game_name = game_type_names.get(game_data['game_type'], game_data['game_type'])
    
    builder.row(
        InlineKeyboardButton(text=f"👤 Игрок: {user_id}", callback_data="noop"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text=f"🎮 {game_name}", callback_data="noop"),
        InlineKeyboardButton(text=f"💰 Ставка: {game_data['bet']}", callback_data="noop"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="✅ Сделать выигрыш", callback_data=f"admin_win_{user_id}"),
        InlineKeyboardButton(text="❌ Сделать проигрыш", callback_data=f"admin_lose_{user_id}"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🎲 Установить значение", callback_data=f"admin_set_dice_{user_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="⏭ Завершить игру", callback_data=f"admin_end_game_{user_id}"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_active_games"),
        width=2
    )
    
    return builder.as_markup()

def get_active_games_list_keyboard():
    """Клавиатура со списком активных игр"""
    builder = InlineKeyboardBuilder()
    
    if not active_games:
        builder.row(
            InlineKeyboardButton(text="📭 Нет активных игр", callback_data="noop"),
            width=1
        )
    else:
        for user_id, game_data in list(active_games.items())[:10]:  # Показываем первые 10
            user = db.get_user(user_id)
            name = user['first_name'] or user['username'] or f"ID {user_id}"
            game_type = game_data['game_type']
            game_emoji = "🎲" if game_type == "guess" else "🎯" if game_type == "highlow" else "🎰" if game_type == "duel" else "🎲🎲"
            
            time_passed = datetime.now() - game_data['start_time']
            minutes = int(time_passed.total_seconds() // 60)
            seconds = int(time_passed.total_seconds() % 60)
            
            builder.row(
                InlineKeyboardButton(
                    text=f"{game_emoji} {name} | {game_data['bet']}💰 | {minutes}:{seconds:02d}",
                    callback_data=f"admin_game_detail_{user_id}"
                ),
                width=1
            )
    
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_active_games"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control"),
        width=2
    )
    
    return builder.as_markup()

def get_dice_value_keyboard(user_id: int):
    """Клавиатура для выбора значения кости"""
    builder = InlineKeyboardBuilder()
    
    # Для разных игр нужны разные значения
    game_data = active_games.get(user_id)
    if not game_data:
        return get_back_keyboard("admin_active_games")
    
    if game_data['game_type'] == 'guess':
        # Для игры "Угадай число" нужно одно значение от 1 до 6
        buttons = []
        for i in range(1, 7):
            buttons.append(InlineKeyboardButton(text=f"{i} {DICE_EMOJIS[i-1]}", callback_data=f"admin_set_value_{user_id}_{i}"))
        
        for i in range(0, len(buttons), 3):
            builder.row(*buttons[i:i+3])
    
    elif game_data['game_type'] == 'highlow':
        # Для игры "Больше/Меньше" тоже одно значение
        buttons = []
        for i in range(1, 7):
            result = "❌ Проигрыш" if i <= 3 else "🔄 Ничья" if i <= 5 else "✅ Выигрыш"
            buttons.append(InlineKeyboardButton(text=f"{i} {DICE_EMOJIS[i-1]} ({result})", callback_data=f"admin_set_value_{user_id}_{i}"))
        
        for button in buttons:
            builder.row(button, width=1)
    
    elif game_data['game_type'] == 'duel':
        # Для дуэли нужно два значения (игрок и бот)
        builder.row(
            InlineKeyboardButton(text="🎲 Задать оба значения", callback_data=f"admin_set_duel_both_{user_id}"),
            width=1
        )
        builder.row(
            InlineKeyboardButton(text="👤 Значение игрока", callback_data=f"admin_set_duel_player_{user_id}"),
            InlineKeyboardButton(text="🤖 Значение бота", callback_data=f"admin_set_duel_bot_{user_id}"),
            width=2
        )
    
    elif game_data['game_type'] == 'craps':
        # Для крэпса нужно сумма двух костей
        builder.row(
            InlineKeyboardButton(text="🎲 Задать результат", callback_data=f"admin_set_craps_{user_id}"),
            width=1
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_game_detail_{user_id}"),
        width=1
    )
    
    return builder.as_markup()

def get_back_keyboard(callback: str):
    """Вспомогательная клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=callback),
        width=1
    )
    return builder.as_markup()

# Функция для регистрации активной игры
def register_active_game(user_id: int, game_type: str, bet: int, message_id: int, chat_id: int):
    """Регистрация активной игры пользователя"""
    active_games[user_id] = {
        "game_type": game_type,
        "bet": bet,
        "start_time": datetime.now(),
        "message_id": message_id,
        "chat_id": chat_id
    }

# Функция для удаления активной игры
def unregister_active_game(user_id: int):
    """Удаление активной игры пользователя"""
    if user_id in active_games:
        del active_games[user_id]

# Функция для принудительного завершения игры с заданным результатом
async def force_game_result(bot, user_id: int, result_data: dict):
    """Принудительное завершение игры с заданным результатом"""
    if user_id not in active_games:
        return False, "Игра не найдена"
    
    game_data = active_games[user_id]
    game_type = game_data['game_type']
    bet = game_data['bet']
    message_id = game_data['message_id']
    chat_id = game_data['chat_id']
    
    try:
        # Списываем ставку, если еще не списана (проверяем по балансу)
        user = db.get_user(user_id)
        if user['balance'] >= bet:
            db.update_balance(user_id, -bet, "bet", f"Ставка в игре {game_type} (принудительно)")
        
        # Формируем результат
        if 'win_amount' in result_data:
            win_amount = result_data['win_amount']
            if win_amount > 0:
                db.update_balance(user_id, win_amount, "win", f"Выигрыш в игре {game_type} (админ)")
                result = "win"
                result_text = result_data.get('text', f"🎲 Результат установлен администратором\n💰 Выигрыш: +{win_amount} монет")
            elif win_amount == bet:
                db.update_balance(user_id, bet, "refund", f"Возврат ставки в игре {game_type} (админ)")
                result = "draw"
                result_text = result_data.get('text', "🔄 Ничья. Ставка возвращена (админ)")
            else:
                result = "loss"
                result_text = result_data.get('text', f"❌ Проигрыш. Потеряно {bet} монет (админ)")
                win_amount = 0
        else:
            # Если не указан win_amount, определяем по результату
            if result_data.get('outcome') == 'win':
                win_amount = bet * (result_data.get('multiplier', 2))
                db.update_balance(user_id, win_amount, "win", f"Выигрыш в игре {game_type} (админ)")
                result = "win"
                result_text = result_data.get('text', f"🎉 Администратор установил выигрыш! +{win_amount} монет")
            elif result_data.get('outcome') == 'draw':
                db.update_balance(user_id, bet, "refund", f"Возврат ставки в игре {game_type} (админ)")
                result = "draw"
                result_text = result_data.get('text', "🔄 Администратор установил ничью")
                win_amount = 0
            else:
                result = "loss"
                result_text = result_data.get('text', f"❌ Администратор установил проигрыш")
                win_amount = 0
        
        # Сохраняем результат игры
        db.add_game_result(user_id, game_type, bet, win_amount, result)
        
        # Обновляем сообщение пользователя
        user = db.get_user(user_id)
        result_text += f"\n\n💰 Текущий баланс: {format_number(user['balance'])} монет"
        
        from keyboards import get_main_keyboard
        is_admin = user.get("is_admin", False) or (user_id in ADMIN_IDS)
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=result_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id, is_admin)
        )
        
        # Удаляем из активных игр
        unregister_active_game(user_id)
        
        return True, "Игра успешно завершена"
        
    except Exception as e:
        return False, f"Ошибка: {e}"

# Обработчики команд
@router.message(Command("active_games"))
async def cmd_active_games(message: types.Message):
    """Команда для просмотра активных игр (только для админов)"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора!")
        return
    
    if not active_games:
        await message.answer("📭 Нет активных игр в данный момент")
        return
    
    text = "🎮 **Активные игры:**\n\n"
    for user_id, game_data in active_games.items():
        user = db.get_user(user_id)
        name = user['first_name'] or user['username'] or f"ID {user_id}"
        game_type = game_data['game_type']
        time_passed = datetime.now() - game_data['start_time']
        minutes = int(time_passed.total_seconds() // 60)
        seconds = int(time_passed.total_seconds() % 60)
        
        text += f"• {name} (ID: `{user_id}`)\n"
        text += f"  🎮 {game_type} | 💰 {game_data['bet']} | ⏱ {minutes}:{seconds:02d}\n\n"
    
    await message.answer(text, parse_mode="Markdown")

@router.callback_query(F.data == "admin_game_control")
async def admin_game_control(callback: types.CallbackQuery):
    """Меню управления играми"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎮 **Управление играми**\n\n"
        "Здесь вы можете просматривать активные игры пользователей\n"
        "и вмешиваться в их результат в реальном времени.",
        parse_mode="Markdown",
        reply_markup=get_admin_game_control_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "admin_active_games")
async def admin_active_games(callback: types.CallbackQuery):
    """Список активных игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🎮 **Активные игры**\n\n"
        "Нажмите на игру для управления:",
        parse_mode="Markdown",
        reply_markup=get_active_games_list_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_game_detail_"))
async def admin_game_detail(callback: types.CallbackQuery):
    """Детальная информация об игре"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    if user_id not in active_games:
        await callback.message.edit_text(
            "❌ Игра больше не активна",
            reply_markup=get_back_keyboard("admin_active_games")
        )
        await callback.answer()
        return
    
    game_data = active_games[user_id]
    user = db.get_user(user_id)
    
    time_passed = datetime.now() - game_data['start_time']
    minutes = int(time_passed.total_seconds() // 60)
    seconds = int(time_passed.total_seconds() % 60)
    
    game_type_names = {
        "guess": "Угадай число",
        "highlow": "Больше/Меньше 3",
        "duel": "Дуэль с ботом",
        "craps": "Крэпс"
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
        reply_markup=get_user_game_control_keyboard(user_id, game_data)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_win_"))
async def admin_force_win(callback: types.CallbackQuery):
    """Принудительный выигрыш"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    game_data = active_games[user_id]
    bet = game_data['bet']
    
    # Определяем множитель в зависимости от игры
    multipliers = {
        "guess": 5,
        "highlow": 2,
        "duel": 2,
        "craps": 1.5
    }
    
    multiplier = multipliers.get(game_data['game_type'], 2)
    win_amount = int(bet * multiplier)
    
    result_data = {
        "win_amount": win_amount,
        "text": f"🎉 **АДМИНИСТРАТОР УСТАНОВИЛ ВЫИГРЫШ!**\n\n💰 Выигрыш: +{win_amount} монет\n🎲 Множитель: x{multiplier}"
    }
    
    success, message = await force_game_result(callback.bot, user_id, result_data)
    
    if success:
        await callback.answer("✅ Выигрыш установлен!", show_alert=True)
        # Обновляем список активных игр
        await admin_active_games(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)

@router.callback_query(F.data.startswith("admin_lose_"))
async def admin_force_lose(callback: types.CallbackQuery):
    """Принудительный проигрыш"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    game_data = active_games[user_id]
    bet = game_data['bet']
    
    result_data = {
        "win_amount": 0,
        "text": f"❌ **АДМИНИСТРАТОР УСТАНОВИЛ ПРОИГРЫШ!**\n\n💸 Потеряно: {bet} монет"
    }
    
    success, message = await force_game_result(callback.bot, user_id, result_data)
    
    if success:
        await callback.answer("✅ Проигрыш установлен!", show_alert=True)
        await admin_active_games(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)

@router.callback_query(F.data.startswith("admin_set_dice_"))
async def admin_set_dice(callback: types.CallbackQuery):
    """Установка значения кости"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"🎲 Выберите значение для игры:\n\n"
        f"Игрок: `{user_id}`",
        parse_mode="Markdown",
        reply_markup=get_dice_value_keyboard(user_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_set_value_"))
async def admin_set_value(callback: types.CallbackQuery):
    """Установка конкретного значения"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[3])
    value = int(parts[4])
    
    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    game_data = active_games[user_id]
    bet = game_data['bet']
    
    # Определяем результат на основе значения
    if game_data['game_type'] == 'guess':
        # Для угадай числа нужно еще знать, что загадал пользователь
        # По умолчанию считаем, что пользователь не угадал
        win_amount = 0
        result_text = f"🎲 Выпало: {value} {DICE_EMOJIS[value-1]}\n\n❌ Администратор установил проигрыш"
        
    elif game_data['game_type'] == 'highlow':
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
        await callback.answer("❌ Этот тип игры не поддерживает одиночное значение", show_alert=True)
        return
    
    result_data = {
        "win_amount": win_amount,
        "text": result_text
    }
    
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
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    if user_id not in active_games:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    game_data = active_games[user_id]
    bet = game_data['bet']
    
    result_data = {
        "win_amount": bet,
        "text": f"🔄 **ИГРА ПРЕРВАНА АДМИНИСТРАТОРОМ**\n\n💰 Ставка возвращена: +{bet} монет"
    }
    
    success, message = await force_game_result(callback.bot, user_id, result_data)
    
    if success:
        await callback.answer("✅ Игра завершена, ставка возвращена", show_alert=True)
        await admin_active_games(callback)
    else:
        await callback.answer(f"❌ {message}", show_alert=True)

@router.callback_query(F.data == "admin_skip_wait")
async def admin_skip_wait(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск ожидания в игре (например, ожидание ввода числа)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👤 Введите ID пользователя, чье ожидание нужно пропустить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control")]
        ])
    )
    await state.set_state(AdminGameControlStates.waiting_for_user_id)
    await state.update_data(action="skip_wait")
    await callback.answer()

@router.callback_query(F.data == "admin_restart_game")
async def admin_restart_game(callback: types.CallbackQuery, state: FSMContext):
    """Перезапуск игры"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👤 Введите ID пользователя для перезапуска игры:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control")]
        ])
    )
    await state.set_state(AdminGameControlStates.waiting_for_user_id)
    await state.update_data(action="restart")
    await callback.answer()

@router.callback_query(F.data == "admin_games_stats")
async def admin_games_stats(callback: types.CallbackQuery):
    """Статистика игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    total_games = db.get_total_games_count()
    
    # Получаем статистику по типам игр
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

@router.message(AdminGameControlStates.waiting_for_user_id)
async def process_user_id_for_game(message: types.Message, state: FSMContext):
    """Обработка ID пользователя для действий с играми"""
    try:
        user_id = int(message.text.strip())
        data = await state.get_data()
        action = data.get("action")
        
        if user_id not in active_games:
            await message.answer(
                f"❌ У пользователя {user_id} нет активных игр",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control")]
                ])
            )
            await state.clear()
            return
        
        game_data = active_games[user_id]
        
        if action == "skip_wait":
            # Здесь можно реализовать пропуск ожидания в конкретной игре
            # Например, автоматически сгенерировать случайное число
            if game_data['game_type'] == 'guess':
                # Автоматически генерируем случайное число
                dice = random.randint(1, 6)
                # Отправляем результат пользователю
                await message.bot.send_message(
                    user_id,
                    f"⏱ Администратор пропустил ожидание. Ваше число: {dice}"
                )
                
            await message.answer(
                f"✅ Ожидание пропущено для пользователя {user_id}",
                reply_markup=get_back_keyboard("admin_game_control")
            )
        
        elif action == "restart":
            # Перезапуск игры (удаляем и предлагаем начать заново)
            unregister_active_game(user_id)
            await message.bot.send_message(
                user_id,
                "🔄 Администратор перезапустил игру. Начните заново."
            )
            await message.answer(
                f"✅ Игра перезапущена для пользователя {user_id}",
                reply_markup=get_back_keyboard("admin_game_control")
            )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Введите корректный ID (число)!",
            reply_markup=get_back_keyboard("admin_game_control")
        )
        await state.clear()