# handlers/levels.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS
from database import db
from utils import format_number

router = Router()

class LevelStates(StatesGroup):
    waiting_for_confirmation = State()

def get_levels_keyboard():
    """Клавиатура для меню уровней"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📊 Мой уровень", callback_data="my_level"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="⬆️ Повысить уровень", callback_data="upgrade_level"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📋 Все уровни", callback_data="all_levels"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Топ по уровням", callback_data="level_leaderboard"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"),
        width=1
    )
    
    return builder.as_markup()

def get_upgrade_confirmation_keyboard(level_number: int, price: int):
    """Клавиатура подтверждения повышения уровня"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_upgrade_{level_number}_{price}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="my_level"),
        width=2
    )
    
    return builder.as_markup()

def get_all_levels_keyboard(levels: list, current_level: int):
    """Клавиатура со списком всех уровней"""
    builder = InlineKeyboardBuilder()
    
    for level in levels:
        level_num = level['number']
        if level_num == current_level:
            status = "✅ ТЕКУЩИЙ"
        elif level_num < current_level:
            status = "✅ Пройден"
        else:
            status = f"💰 {format_number(level['price'])} монет"
        
        builder.row(
            InlineKeyboardButton(
                text=f"{level['name']} - {status}",
                callback_data=f"level_info_{level_num}"
            ),
            width=1
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="level_menu"),
        width=1
    )
    
    return builder.as_markup()

def get_level_leaderboard_keyboard():
    """Клавиатура для топа уровней"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="level_leaderboard"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="level_menu"),
        width=1
    )
    
    return builder.as_markup()

@router.message(Command("level"))
async def cmd_level(message: types.Message):
    """Команда для открытия меню уровней"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        await message.answer("❌ Ошибка загрузки профиля")
        return
    
    user_level = db.get_user_level(user_id)
    
    text = (
        f"🎚️ **Система уровней**\n\n"
        f"Повышайте свой уровень, чтобы увеличить удачу в играх!\n"
        f"С каждым уровнем растет шанс на дополнительный бонус.\n\n"
        f"**Ваш текущий уровень:**\n"
        f"• {user_level['level_name']}\n"
        f"• Множитель удачи: x{user_level['luck_multiplier']}\n"
        f"• Всего потрачено: {format_number(user_level['total_spent'])} монет\n\n"
        f"Выберите действие:"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_levels_keyboard()
    )

@router.callback_query(F.data == "level_menu")
async def level_menu(callback: types.CallbackQuery):
    """Меню уровней"""
    user_id = callback.from_user.id
    user_level = db.get_user_level(user_id)
    
    text = (
        f"🎚️ **Система уровней**\n\n"
        f"**Ваш текущий уровень:**\n"
        f"• {user_level['level_name']}\n"
        f"• Множитель удачи: x{user_level['luck_multiplier']}\n"
        f"• Всего потрачено: {format_number(user_level['total_spent'])} монет\n\n"
        f"Выберите действие:"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_levels_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "my_level")
async def my_level(callback: types.CallbackQuery):
    """Информация о текущем уровне"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)
    
    text = (
        f"📊 **Ваш уровень**\n\n"
        f"**Текущий уровень:** {user_level['level_name']}\n"
        f"**Множитель удачи:** x{user_level['luck_multiplier']}\n"
        f"**Всего потрачено:** {format_number(user_level['total_spent'])} монет\n"
        f"**Баланс:** {format_number(user['balance'])} монет\n\n"
    )
    
    if user_level['next_level']:
        next_level = user_level['next_level']
        text += (
            f"**Следующий уровень:** {next_level['name']}\n"
            f"**Цена:** {format_number(next_level['price'])} монет\n"
            f"**Новый множитель:** x{next_level['luck_multiplier']}\n"
            f"**Нужно монет:** {format_number(next_level['price'])}\n"
        )
        
        if user['balance'] >= next_level['price']:
            text += f"\n✅ Вы можете повысить уровень!"
        else:
            need = next_level['price'] - user['balance']
            text += f"\n❌ Не хватает {format_number(need)} монет"
    else:
        text += f"\n🏆 Вы достигли максимального уровня!"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬆️ Повысить уровень", callback_data="upgrade_level")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="level_menu")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "upgrade_level")
async def upgrade_level(callback: types.CallbackQuery):
    """Повышение уровня"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)
    
    if not user_level['next_level']:
        await callback.message.edit_text(
            "🏆 Вы уже достигли максимального уровня!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="my_level")]
            ])
        )
        await callback.answer()
        return
    
    next_level = user_level['next_level']
    
    if user['balance'] < next_level['price']:
        need = next_level['price'] - user['balance']
        await callback.message.edit_text(
            f"❌ Недостаточно монет!\n\n"
            f"**Требуется:** {format_number(next_level['price'])} монет\n"
            f"**Ваш баланс:** {format_number(user['balance'])} монет\n"
            f"**Не хватает:** {format_number(need)} монет",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="my_level")]
            ])
        )
        await callback.answer()
        return
    
    text = (
        f"⬆️ **Повышение уровня**\n\n"
        f"Вы хотите повысить уровень до **{next_level['name']}**?\n\n"
        f"**Цена:** {format_number(next_level['price'])} монет\n"
        f"**Текущий множитель:** x{user_level['luck_multiplier']}\n"
        f"**Новый множитель:** x{next_level['luck_multiplier']}\n\n"
        f"Подтвердите действие:"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_upgrade_confirmation_keyboard(next_level['number'], next_level['price'])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_upgrade_"))
async def confirm_upgrade(callback: types.CallbackQuery):
    """Подтверждение повышения уровня"""
    try:
        parts = callback.data.split("_")
        level_number = int(parts[2])
        price = int(parts[3])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    # Проверяем баланс еще раз
    if user['balance'] < price:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        await my_level(callback)
        return
    
    # Повышаем уровень
    result = db.upgrade_user_level(user_id)
    
    if result['success']:
        await callback.message.edit_text(
            f"✅ **Уровень повышен!**\n\n"
            f"**Новый уровень:** {result['level_name']}\n"
            f"**Новый множитель удачи:** x{result['new_luck']}\n"
            f"**Потрачено:** {format_number(price)} монет\n\n"
            f"Теперь ваша удача увеличилась! ✨",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Мой уровень", callback_data="my_level")],
                [InlineKeyboardButton(text="🔙 В меню", callback_data="level_menu")]
            ])
        )
    else:
        await callback.message.edit_text(
            f"❌ Ошибка: {result['message']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="my_level")]
            ])
        )
    
    await callback.answer()

@router.callback_query(F.data == "all_levels")
async def all_levels(callback: types.CallbackQuery):
    """Список всех уровней"""
    user_id = callback.from_user.id
    user_level = db.get_user_level(user_id)
    all_levels = db.get_all_levels()
    
    text = "📋 **Все уровни**\n\n"
    
    for level in all_levels:
        level_num = level['number']
        if level_num == user_level['current_level']:
            status = "✅ ТЕКУЩИЙ"
        elif level_num < user_level['current_level']:
            status = "✅ Пройден"
        else:
            status = f"💰 {format_number(level['price'])} монет"
        
        text += f"**{level['name']}** - {status}\n"
        text += f"└ Множитель: x{level['luck_multiplier']}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="level_menu")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data == "level_leaderboard")
async def level_leaderboard(callback: types.CallbackQuery):
    """Топ игроков по уровню"""
    leaderboard = db.get_level_leaderboard(10)
    
    if not leaderboard:
        await callback.message.edit_text(
            "🏆 **Топ игроков по уровню**\n\n"
            "Пока нет данных",
            reply_markup=get_level_leaderboard_keyboard()
        )
        await callback.answer()
        return
    
    text = "🏆 **Топ игроков по уровню**\n\n"
    
    for player in leaderboard:
        name = player['first_name'] or player['username'] or f"Игрок {player['user_id']}"
        medal = "🥇" if player['position'] == 1 else "🥈" if player['position'] == 2 else "🥉" if player['position'] == 3 else f"{player['position']}."
        
        text += f"{medal} **{name}**\n"
        text += f"   ├ Уровень: {player['level_name']}\n"
        text += f"   ├ Множитель: x{player['luck_multiplier']}\n"
        text += f"   └ Потрачено: {format_number(player['total_spent'])} монет\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_level_leaderboard_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("level_info_"))
async def level_info(callback: types.CallbackQuery):
    """Информация о конкретном уровне"""
    try:
        level_num = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return
    
    level = db.get_level(level_num)
    if not level:
        await callback.answer("❌ Уровень не найден", show_alert=True)
        return
    
    user_id = callback.from_user.id
    user_level = db.get_user_level(user_id)
    
    text = (
        f"📊 **Информация об уровне**\n\n"
        f"**{level['name']}**\n"
        f"**Множитель удачи:** x{level['luck_multiplier']}\n"
        f"**Цена повышения:** {format_number(level['price'])} монет\n\n"
        f"{level['description']}\n\n"
    )
    
    if level_num == user_level['current_level']:
        text += "✅ Это ваш текущий уровень"
    elif level_num < user_level['current_level']:
        text += "✅ Вы уже прошли этот уровень"
    else:
        if level_num == user_level['current_level'] + 1:
            text += f"💰 Следующий уровень! Нужно {format_number(level['price'])} монет"
        else:
            text += f"🔒 Будет доступен после предыдущих уровней"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="all_levels")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()