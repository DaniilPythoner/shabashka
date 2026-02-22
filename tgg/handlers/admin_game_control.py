# handlers/admin_game_control.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import random
import logging

from config import ADMIN_IDS
from database import db
from utils import format_number, DICE_EMOJIS, roll_dice

logger = logging.getLogger(__name__)

router = Router()

# Хранилище активных игр пользователей
# Структура: {user_id: {"game_type": str, "bet": int, "start_time": datetime, 
#                       "message_id": int, "chat_id": int, "admin_intervention": dict}}
active_games = {}

# Хранилище настроек вмешательства для пользователей
# Структура: {user_id: {"force_lose": bool, "force_win": bool, "force_value": int, "blocked_numbers": list}}
user_interventions = {}

class AdminGameControlStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_force_value = State()
    waiting_for_blocked_number = State()

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    if user_id in ADMIN_IDS:
        return True
    user = db.get_user(user_id)
    return user and user.get("is_admin", False)

def register_active_game(user_id: int, game_type: str, bet: int, message_id: int, chat_id: int):
    """Регистрация активной игры пользователя"""
    active_games[user_id] = {
        "game_type": game_type,
        "bet": bet,
        "start_time": datetime.now(),
        "message_id": message_id,
        "chat_id": chat_id,
        "admin_intervention": None
    }

def unregister_active_game(user_id: int):
    """Удаление активной игры пользователя"""
    if user_id in active_games:
        del active_games[user_id]

def set_user_force_lose(user_id: int, active: bool = True):
    """Установка принудительного проигрыша для пользователя"""
    if user_id not in user_interventions:
        user_interventions[user_id] = {
            "force_lose": False,
            "force_win": False,
            "force_value": None,
            "blocked_numbers": []
        }
    user_interventions[user_id]["force_lose"] = active
    # Сбрасываем другие режимы
    if active:
        user_interventions[user_id]["force_win"] = False
        user_interventions[user_id]["force_value"] = None

def set_user_force_win(user_id: int, active: bool = True):
    """Установка принудительного выигрыша для пользователя"""
    if user_id not in user_interventions:
        user_interventions[user_id] = {
            "force_lose": False,
            "force_win": False,
            "force_value": None,
            "blocked_numbers": []
        }
    user_interventions[user_id]["force_win"] = active
    # Сбрасываем другие режимы
    if active:
        user_interventions[user_id]["force_lose"] = False
        user_interventions[user_id]["force_value"] = None

def set_user_force_value(user_id: int, value: int):
    """Установка принудительного значения для игры"""
    if user_id not in user_interventions:
        user_interventions[user_id] = {
            "force_lose": False,
            "force_win": False,
            "force_value": None,
            "blocked_numbers": []
        }
    user_interventions[user_id]["force_value"] = value
    # Сбрасываем другие режимы
    user_interventions[user_id]["force_lose"] = False
    user_interventions[user_id]["force_win"] = False

def add_blocked_number(user_id: int, number: int):
    """Добавление заблокированного числа для пользователя"""
    if user_id not in user_interventions:
        user_interventions[user_id] = {
            "force_lose": False,
            "force_win": False,
            "force_value": None,
            "blocked_numbers": []
        }
    if number not in user_interventions[user_id]["blocked_numbers"]:
        user_interventions[user_id]["blocked_numbers"].append(number)

def remove_blocked_number(user_id: int, number: int):
    """Удаление заблокированного числа"""
    if user_id in user_interventions and number in user_interventions[user_id]["blocked_numbers"]:
        user_interventions[user_id]["blocked_numbers"].remove(number)

def clear_user_intervention(user_id: int):
    """Очистка всех настроек вмешательства для пользователя"""
    if user_id in user_interventions:
        user_interventions[user_id] = {
            "force_lose": False,
            "force_win": False,
            "force_value": None,
            "blocked_numbers": []
        }

def get_user_intervention(user_id: int) -> dict:
    """Получение настроек вмешательства для пользователя"""
    return user_interventions.get(user_id, {
        "force_lose": False,
        "force_win": False,
        "force_value": None,
        "blocked_numbers": []
    })

def apply_intervention_to_dice(user_id: int, game_type: str, player_guess: int = None) -> int:
    """
    Применение настроек вмешательства к броску кости
    Возвращает модифицированное значение кости
    """
    intervention = get_user_intervention(user_id)
    
    # Принудительный проигрыш для игры "Угадай число"
    if intervention["force_lose"] and game_type == "guess" and player_guess is not None:
        # Генерируем любое число, кроме выбранного игроком
        possible_values = [1, 2, 3, 4, 5, 6]
        possible_values.remove(player_guess)
        return random.choice(possible_values)
    
    # Принудительный выигрыш для игры "Угадай число"
    elif intervention["force_win"] and game_type == "guess" and player_guess is not None:
        # Возвращаем число, которое выбрал игрок
        return player_guess
    
    # Принудительное значение
    elif intervention["force_value"] is not None:
        return intervention["force_value"]
    
    # Заблокированные числа
    elif intervention["blocked_numbers"] and game_type == "guess" and player_guess is not None:
        # Если число, которое выбрал игрок, заблокировано - даем любое другое
        if player_guess in intervention["blocked_numbers"]:
            possible_values = [1, 2, 3, 4, 5, 6]
            for blocked in intervention["blocked_numbers"]:
                if blocked in possible_values:
                    possible_values.remove(blocked)
            if possible_values:
                return random.choice(possible_values)
    
    # Случайное значение по умолчанию
    return roll_dice()

def apply_intervention_to_duel(user_id: int, player_sum: int, bot_sum: int) -> tuple:
    """
    Применение настроек вмешательства к дуэли
    Возвращает модифицированные значения (player_sum, bot_sum, результат)
    """
    intervention = get_user_intervention(user_id)
    
    if intervention["force_lose"]:
        # Принудительный проигрыш - делаем так, чтобы бот выиграл
        if player_sum > bot_sum:
            # Меняем значения местами или увеличиваем сумму бота
            return player_sum, player_sum + random.randint(1, 3), "lose"
        elif player_sum == bot_sum:
            # Увеличиваем сумму бота
            return player_sum, player_sum + random.randint(1, 3), "lose"
        else:
            # Бот уже выигрывает
            return player_sum, bot_sum, "lose"
    
    elif intervention["force_win"]:
        # Принудительный выигрыш - делаем так, чтобы игрок выиграл
        if player_sum < bot_sum:
            # Увеличиваем сумму игрока
            return bot_sum + random.randint(1, 3), bot_sum, "win"
        elif player_sum == bot_sum:
            # Увеличиваем сумму игрока
            return bot_sum + random.randint(1, 3), bot_sum, "win"
        else:
            # Игрок уже выигрывает
            return player_sum, bot_sum, "win"
    
    return player_sum, bot_sum, None

def apply_intervention_to_highlow(user_id: int, dice: int) -> int:
    """
    Применение настроек вмешательства к игре "Больше/Меньше"
    Возвращает модифицированное значение кости
    """
    intervention = get_user_intervention(user_id)
    
    if intervention["force_lose"]:
        # Принудительный проигрыш - выдаем 1-3
        return random.choice([1, 2, 3])
    
    elif intervention["force_win"]:
        # Принудительный выигрыш - выдаем 6
        return 6
    
    elif intervention["force_value"] is not None:
        return intervention["force_value"]
    
    return dice

def apply_intervention_to_craps(user_id: int, dice1: int, dice2: int) -> tuple:
    """
    Применение настроек вмешательства к игре "Крэпс"
    Возвращает модифицированные значения костей
    """
    intervention = get_user_intervention(user_id)
    total = dice1 + dice2
    
    if intervention["force_lose"]:
        # Принудительный проигрыш
        losing_totals = [2, 3, 12]
        target_total = random.choice(losing_totals)
        # Генерируем комбинацию, дающую нужную сумму
        return _get_dice_combination(target_total)
    
    elif intervention["force_win"]:
        # Принудительный выигрыш
        winning_totals = [7, 11]
        target_total = random.choice(winning_totals)
        return _get_dice_combination(target_total)
    
    elif intervention["force_value"] is not None:
        return _get_dice_combination(intervention["force_value"])
    
    return dice1, dice2

def _get_dice_combination(target_sum: int) -> tuple:
    """Вспомогательная функция для получения комбинации костей с заданной суммой"""
    if target_sum < 2 or target_sum > 12:
        return (1, 1)
    
    if target_sum <= 7:
        d1 = random.randint(1, target_sum - 1)
        d2 = target_sum - d1
        if d2 > 6:
            d1 = target_sum - 6
            d2 = 6
    else:
        d1 = random.randint(target_sum - 6, 6)
        d2 = target_sum - d1
    
    return (d1, d2)

def get_active_games_list_keyboard():
    """Клавиатура со списком активных игр"""
    builder = InlineKeyboardBuilder()
    
    if not active_games:
        builder.row(
            InlineKeyboardButton(text="📭 Нет активных игр", callback_data="noop"),
            width=1
        )
    else:
        for user_id, game_data in list(active_games.items())[:10]:
            user = db.get_user(user_id)
            name = user['first_name'] or user['username'] or f"ID {user_id}"
            game_type = game_data['game_type']
            game_emoji = "🎲" if game_type == "guess" else "🎯" if game_type == "highlow" else "🎰" if game_type == "duel" else "🎲🎲"
            
            time_passed = datetime.now() - game_data['start_time']
            minutes = int(time_passed.total_seconds() // 60)
            seconds = int(time_passed.total_seconds() % 60)
            
            # Проверяем наличие активного вмешательства
            intervention = get_user_intervention(user_id)
            intervention_icon = ""
            if intervention["force_lose"]:
                intervention_icon = " ⚠️(принудительный проигрыш)"
            elif intervention["force_win"]:
                intervention_icon = " ⚠️(принудительный выигрыш)"
            elif intervention["force_value"]:
                intervention_icon = f" ⚠️(фикс. значение {intervention['force_value']})"
            elif intervention["blocked_numbers"]:
                intervention_icon = f" ⚠️(заблокированы {intervention['blocked_numbers']})"
            
            builder.row(
                InlineKeyboardButton(
                    text=f"{game_emoji} {name[:15]} | {game_data['bet']}💰 | {minutes}:{seconds:02d}{intervention_icon}",
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

def get_user_game_control_keyboard(user_id: int, game_data: dict):
    """Клавиатура для управления конкретной игрой пользователя"""
    builder = InlineKeyboardBuilder()
    
    intervention = get_user_intervention(user_id)
    
    # Индикаторы активных настроек
    status_row = []
    if intervention["force_lose"]:
        status_row.append(InlineKeyboardButton(text="⚠️ Режим: проигрыш", callback_data="noop"))
    elif intervention["force_win"]:
        status_row.append(InlineKeyboardButton(text="⚠️ Режим: выигрыш", callback_data="noop"))
    elif intervention["force_value"]:
        status_row.append(InlineKeyboardButton(text=f"⚠️ Фикс. значение: {intervention['force_value']}", callback_data="noop"))
    elif intervention["blocked_numbers"]:
        status_row.append(InlineKeyboardButton(text=f"⚠️ Блок: {intervention['blocked_numbers']}", callback_data="noop"))
    
    if status_row:
        builder.row(*status_row, width=1)
    
    # Основные кнопки управления
    builder.row(
        InlineKeyboardButton(text="❌ Принудительный проигрыш", callback_data=f"admin_force_lose_{user_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="✅ Принудительный выигрыш", callback_data=f"admin_force_win_{user_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🎲 Установить значение", callback_data=f"admin_set_dice_{user_id}"),
        width=1
    )
    
    if game_data['game_type'] == 'guess':
        builder.row(
            InlineKeyboardButton(text="🚫 Заблокировать число", callback_data=f"admin_block_number_{user_id}"),
            width=1
        )
    
    builder.row(
        InlineKeyboardButton(text="🔄 Сбросить настройки", callback_data=f"admin_reset_intervention_{user_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_active_games"),
        width=1
    )
    
    return builder.as_markup()

def get_dice_value_keyboard(user_id: int):
    """Клавиатура для выбора значения кости"""
    builder = InlineKeyboardBuilder()
    
    game_data = active_games.get(user_id)
    if not game_data:
        builder.row(
            InlineKeyboardButton(text="❌ Игра не найдена", callback_data="noop"),
            width=1
        )
        builder.row(
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_active_games"),
            width=1
        )
        return builder.as_markup()
    
    if game_data['game_type'] in ['guess', 'highlow']:
        # Для игр с одним значением
        buttons = []
        for i in range(1, 7):
            buttons.append(InlineKeyboardButton(
                text=f"{i} {DICE_EMOJIS[i-1]}", 
                callback_data=f"admin_set_value_{user_id}_{i}"
            ))
        
        for i in range(0, len(buttons), 3):
            builder.row(*buttons[i:i+3])
    
    elif game_data['game_type'] == 'duel':
        # Для дуэли можно установить обе кости или только результат
        builder.row(
            InlineKeyboardButton(text="🎲 Установить обе кости", callback_data=f"admin_set_duel_both_{user_id}"),
            width=1
        )
        builder.row(
            InlineKeyboardButton(text="👤 Кости игрока", callback_data=f"admin_set_player_dice_{user_id}"),
            InlineKeyboardButton(text="🤖 Кости бота", callback_data=f"admin_set_bot_dice_{user_id}"),
            width=2
        )
    
    elif game_data['game_type'] == 'craps':
        # Для крэпса нужно установить сумму
        buttons = []
        for total in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
            buttons.append(InlineKeyboardButton(
                text=f"{total}", 
                callback_data=f"admin_set_craps_{user_id}_{total}"
            ))
        
        for i in range(0, len(buttons), 4):
            builder.row(*buttons[i:i+4])
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_game_detail_{user_id}"),
        width=1
    )
    
    return builder.as_markup()

def get_block_number_keyboard(user_id: int):
    """Клавиатура для блокировки чисел"""
    builder = InlineKeyboardBuilder()
    
    intervention = get_user_intervention(user_id)
    blocked = intervention["blocked_numbers"]
    
    buttons = []
    for i in range(1, 7):
        status = "✅" if i in blocked else "⬜"
        buttons.append(InlineKeyboardButton(
            text=f"{status} {i} {DICE_EMOJIS[i-1]}", 
            callback_data=f"admin_toggle_block_{user_id}_{i}"
        ))
    
    for i in range(0, len(buttons), 3):
        builder.row(*buttons[i:i+3])
    
    builder.row(
        InlineKeyboardButton(text="✅ Заблокировать все", callback_data=f"admin_block_all_{user_id}"),
        InlineKeyboardButton(text="❌ Разблокировать все", callback_data=f"admin_unblock_all_{user_id}"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_game_detail_{user_id}"),
        width=1
    )
    
    return builder.as_markup()

# ============================================
# ОБРАБОТЧИКИ
# ============================================

@router.message(Command("active_games"))
async def cmd_active_games(message: types.Message):
    """Команда для просмотра активных игр"""
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
        "и вмешиваться в их результат в реальном времени.\n\n"
        f"**Активных игр:** {len(active_games)}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Активные игры", callback_data="admin_active_games")],
            [InlineKeyboardButton(text="👤 Поиск игры по ID", callback_data="admin_search_game")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "admin_active_games")
async def admin_active_games(callback: types.CallbackQuery):
    """Список активных игр"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
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

@router.callback_query(F.data.startswith("admin_game_detail_"))
async def admin_game_detail(callback: types.CallbackQuery):
    """Детальная информация об игре"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split("_")[3])
    except (IndexError, ValueError):
        await callback.answer("❌ Некорректный ID пользователя", show_alert=True)
        return
    
    if user_id not in active_games:
        await callback.message.edit_text(
            "❌ Игра больше не активна",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К списку игр", callback_data="admin_active_games")]
            ])
        )
        await callback.answer()
        return
    
    game_data = active_games[user_id]
    user = db.get_user(user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    time_passed = datetime.now() - game_data['start_time']
    minutes = int(time_passed.total_seconds() // 60)
    seconds = int(time_passed.total_seconds() % 60)
    
    game_type_names = {
        "guess": "🎲 Угадай число",
        "highlow": "🎯 Больше/Меньше 3",
        "duel": "🎰 Дуэль с ботом",
        "craps": "🎲🎲 Крэпс"
    }
    
    game_name = game_type_names.get(game_data['game_type'], game_data['game_type'])
    
    text = (
        f"🎮 **Детали игры**\n\n"
        f"👤 **Игрок:** {user['first_name'] or user['username'] or 'Неизвестно'}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"💰 **Баланс:** {format_number(user['balance'])} монет\n\n"
        f"**Информация об игре:**\n"
        f"• Тип: {game_name}\n"
        f"• Ставка: {game_data['bet']} монет\n"
        f"• Длительность: {minutes} мин {seconds} сек\n"
        f"• Начало: {game_data['start_time'].strftime('%H:%M:%S')}\n\n"
        f"**Выберите действие:**"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_user_game_control_keyboard(user_id, game_data)
    )
    await callback.answer()

@router.callback_query(F.data == "admin_search_game")
async def admin_search_game(callback: types.CallbackQuery, state: FSMContext):
    """Поиск игры по ID пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👤 Введите ID пользователя для просмотра игры:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control")]
        ])
    )
    await state.set_state(AdminGameControlStates.waiting_for_user_id)
    await state.update_data(action="game_detail")
    await callback.answer()

@router.message(AdminGameControlStates.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    """Обработка введенного ID пользователя"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора!")
        await state.clear()
        return
    
    try:
        target_id = int(message.text.strip())
        data = await state.get_data()
        action = data.get("action")
        
        if action == "game_detail":
            if target_id not in active_games:
                await message.answer(
                    f"❌ У пользователя {target_id} нет активных игр",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control")]
                    ])
                )
                await state.clear()
                return
            
            game_data = active_games[target_id]
            user = db.get_user(target_id)
            
            time_passed = datetime.now() - game_data['start_time']
            minutes = int(time_passed.total_seconds() // 60)
            seconds = int(time_passed.total_seconds() % 60)
            
            game_type_names = {
                "guess": "🎲 Угадай число",
                "highlow": "🎯 Больше/Меньше 3",
                "duel": "🎰 Дуэль с ботом",
                "craps": "🎲🎲 Крэпс"
            }
            
            game_name = game_type_names.get(game_data['game_type'], game_data['game_type'])
            
            text = (
                f"🎮 **Детали игры**\n\n"
                f"👤 **Игрок:** {user['first_name'] or user['username'] or 'Неизвестно'}\n"
                f"🆔 **ID:** `{target_id}`\n"
                f"💰 **Баланс:** {format_number(user['balance'])} монет\n\n"
                f"**Информация об игре:**\n"
                f"• Тип: {game_name}\n"
                f"• Ставка: {game_data['bet']} монет\n"
                f"• Длительность: {minutes} мин {seconds} сек\n\n"
                f"**Выберите действие:**"
            )
            
            await message.answer(
                text,
                parse_mode="Markdown",
                reply_markup=get_user_game_control_keyboard(target_id, game_data)
            )
            await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Введите корректный ID (число)!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_game_control")]
            ])
        )
        await state.clear()

@router.callback_query(F.data.startswith("admin_force_lose_"))
async def admin_force_lose(callback: types.CallbackQuery):
    """Установка принудительного проигрыша для пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    set_user_force_lose(user_id, True)
    
    await callback.answer("✅ Принудительный проигрыш установлен! Игрок будет проигрывать в следующих играх.", show_alert=True)
    
    # Обновляем детали игры
    await admin_game_detail(callback)

@router.callback_query(F.data.startswith("admin_force_win_"))
async def admin_force_win(callback: types.CallbackQuery):
    """Установка принудительного выигрыша для пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    set_user_force_win(user_id, True)
    
    await callback.answer("✅ Принудительный выигрыш установлен! Игрок будет выигрывать в следующих играх.", show_alert=True)
    
    # Обновляем детали игры
    await admin_game_detail(callback)

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
    
    set_user_force_value(user_id, value)
    
    await callback.answer(f"✅ Установлено фиксированное значение {value} для следующих игр!", show_alert=True)
    
    # Обновляем детали игры
    await admin_game_detail(callback)

@router.callback_query(F.data.startswith("admin_set_craps_"))
async def admin_set_craps(callback: types.CallbackQuery):
    """Установка суммы для крэпса"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[3])
    total = int(parts[4])
    
    set_user_force_value(user_id, total)
    
    await callback.answer(f"✅ Установлена фиксированная сумма {total} для крэпса!", show_alert=True)
    
    # Обновляем детали игры
    await admin_game_detail(callback)

@router.callback_query(F.data.startswith("admin_block_number_"))
async def admin_block_number(callback: types.CallbackQuery):
    """Меню блокировки чисел"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    await callback.message.edit_text(
        f"🚫 **Блокировка чисел для пользователя**\n\n"
        f"Выберите числа, которые НЕ должны выпадать игроку:\n"
        f"(заблокированные числа отмечены ✅)",
        parse_mode="Markdown",
        reply_markup=get_block_number_keyboard(user_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_toggle_block_"))
async def admin_toggle_block(callback: types.CallbackQuery):
    """Включение/выключение блокировки числа"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[3])
    number = int(parts[4])
    
    intervention = get_user_intervention(user_id)
    
    if number in intervention["blocked_numbers"]:
        intervention["blocked_numbers"].remove(number)
    else:
        intervention["blocked_numbers"].append(number)
    
    user_interventions[user_id] = intervention
    
    await callback.message.edit_reply_markup(
        reply_markup=get_block_number_keyboard(user_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_block_all_"))
async def admin_block_all(callback: types.CallbackQuery):
    """Блокировка всех чисел"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    intervention = get_user_intervention(user_id)
    intervention["blocked_numbers"] = [1, 2, 3, 4, 5, 6]
    user_interventions[user_id] = intervention
    
    await callback.message.edit_reply_markup(
        reply_markup=get_block_number_keyboard(user_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_unblock_all_"))
async def admin_unblock_all(callback: types.CallbackQuery):
    """Разблокировка всех чисел"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    intervention = get_user_intervention(user_id)
    intervention["blocked_numbers"] = []
    user_interventions[user_id] = intervention
    
    await callback.message.edit_reply_markup(
        reply_markup=get_block_number_keyboard(user_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_reset_intervention_"))
async def admin_reset_intervention(callback: types.CallbackQuery):
    """Сброс всех настроек вмешательства"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    clear_user_intervention(user_id)
    
    await callback.answer("✅ Все настройки вмешательства сброшены!", show_alert=True)
    
    # Обновляем детали игры
    await admin_game_detail(callback)

@router.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    """Заглушка для неактивных кнопок"""
    await callback.answer()