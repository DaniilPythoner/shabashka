# handlers/admin_levels.py
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from config import ADMIN_IDS
from database import db
from utils import format_number, get_level_name_with_emoji

router = Router()


# Состояния для FSM
class AdminLevelsStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_new_level = State()
    waiting_for_confirm = State()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    if user_id in ADMIN_IDS:
        return True
    user = db.get_user(user_id)
    return user and user.get("is_admin", False)


def get_admin_levels_keyboard():
    """Клавиатура управления уровнями для админа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📊 Статистика уровней", callback_data="admin_levels_stats"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="👥 Топ по уровням", callback_data="admin_levels_top"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="⬆️ Повысить уровень", callback_data="admin_levels_upgrade"
        ),
        InlineKeyboardButton(
            text="⬇️ Понизить уровень", callback_data="admin_levels_downgrade"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(
            text="🔄 Сбросить уровень", callback_data="admin_levels_reset"
        ),
        InlineKeyboardButton(
            text="🔍 Проверить уровень", callback_data="admin_levels_check"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(
            text="💰 Изменить потраченное", callback_data="admin_levels_spent"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"), width=1
    )

    return builder.as_markup()


def get_level_selection_keyboard(levels: list, action: str, user_id: int):
    """Клавиатура для выбора уровня"""
    builder = InlineKeyboardBuilder()

    for level in levels:
        level_num = level["number"]
        builder.row(
            InlineKeyboardButton(
                text=f"{level['name']} (x{level['luck_multiplier']})",
                callback_data=f"admin_level_select_{action}_{user_id}_{level_num}",
            ),
            width=1,
        )

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_levels_menu"),
        width=1,
    )

    return builder.as_markup()


def get_confirm_keyboard(user_id: int, new_level: int, action: str):
    """Клавиатура подтверждения изменения уровня"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"admin_level_confirm_{user_id}_{new_level}_{action}",
        ),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_levels_menu"),
        width=2,
    )

    return builder.as_markup()


def get_back_keyboard(callback: str):
    """Клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=callback), width=1)
    return builder.as_markup()


@router.message(Command("admin_levels"))
async def cmd_admin_levels(message: types.Message):
    """Команда для открытия меню управления уровнями"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора!")
        return

    await message.answer(
        "🎚️ **Управление уровнями пользователей**\n\n" "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_levels_keyboard(),
    )


@router.callback_query(F.data == "admin_levels_menu")
async def admin_levels_menu(callback: types.CallbackQuery):
    """Меню управления уровнями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "🎚️ **Управление уровнями пользователей**\n\n" "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_levels_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_levels_stats")
async def admin_levels_stats(callback: types.CallbackQuery):
    """Статистика по уровням"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    # Получаем всех пользователей
    all_users = db.get_all_users(limit=10000)
    levels_count = {}
    total_users = len(all_users)

    # Подсчитываем количество пользователей на каждом уровне
    for user in all_users:
        user_level = db.get_user_level(user["user_id"])
        level_num = user_level["current_level"]
        levels_count[level_num] = levels_count.get(level_num, 0) + 1

    # Получаем информацию об уровнях
    all_levels = db.get_all_levels()

    text = "📊 **Статистика распределения уровней**\n\n"
    text += f"👥 Всего пользователей: {total_users}\n\n"

    for level in all_levels:
        level_num = level["number"]
        count = levels_count.get(level_num, 0)
        percentage = (count / total_users * 100) if total_users > 0 else 0

        # Создаем прогресс-бар
        progress = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))

        text += f"**{level['name']}:**\n"
        text += f"  ├ 👤 {count} пользователей ({percentage:.1f}%)\n"
        text += f"  └ {progress}\n\n"

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard("admin_levels_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "admin_levels_top")
async def admin_levels_top(callback: types.CallbackQuery):
    """Топ пользователей по уровню (для админа)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    leaderboard = db.get_level_leaderboard(20)

    if not leaderboard:
        await callback.message.edit_text(
            "🏆 **Топ пользователей по уровню**\n\n" "Пока нет данных",
            reply_markup=get_back_keyboard("admin_levels_menu"),
        )
        await callback.answer()
        return

    text = "🏆 **Топ пользователей по уровню**\n\n"

    for player in leaderboard:
        name = player["first_name"] or player["username"] or f"ID {player['user_id']}"
        medal = (
            "🥇"
            if player["position"] == 1
            else (
                "🥈"
                if player["position"] == 2
                else "🥉" if player["position"] == 3 else f"{player['position']}."
            )
        )

        level_display = get_level_name_with_emoji(player["level"], player["level_name"])

        text += f"{medal} **{name}**\n"
        text += f"   ├ ID: `{player['user_id']}`\n"
        text += f"   ├ {level_display}\n"
        text += f"   ├ Множитель: x{player['luck_multiplier']}\n"
        text += f"   ├ Потрачено: {format_number(player['total_spent'])} монет\n"
        text += f"   └ Баланс: {format_number(player['balance'])} монет\n\n"

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard("admin_levels_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "admin_levels_upgrade")
async def admin_levels_upgrade(callback: types.CallbackQuery, state: FSMContext):
    """Повышение уровня пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "⬆️ **Повышение уровня**\n\n"
        "Введите ID пользователя, которому хотите повысить уровень:",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("admin_levels_menu"),
    )
    await state.set_state(AdminLevelsStates.waiting_for_user_id)
    await state.update_data(action="upgrade")
    await callback.answer()


@router.callback_query(F.data == "admin_levels_downgrade")
async def admin_levels_downgrade(callback: types.CallbackQuery, state: FSMContext):
    """Понижение уровня пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "⬇️ **Понижение уровня**\n\n"
        "Введите ID пользователя, которому хотите понизить уровень:",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("admin_levels_menu"),
    )
    await state.set_state(AdminLevelsStates.waiting_for_user_id)
    await state.update_data(action="downgrade")
    await callback.answer()


@router.callback_query(F.data == "admin_levels_reset")
async def admin_levels_reset(callback: types.CallbackQuery, state: FSMContext):
    """Сброс уровня пользователя до 1"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "🔄 **Сброс уровня**\n\n"
        "Введите ID пользователя, уровень которого хотите сбросить до 1:",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("admin_levels_menu"),
    )
    await state.set_state(AdminLevelsStates.waiting_for_user_id)
    await state.update_data(action="reset")
    await callback.answer()


@router.callback_query(F.data == "admin_levels_check")
async def admin_levels_check(callback: types.CallbackQuery, state: FSMContext):
    """Проверка уровня пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "🔍 **Проверка уровня**\n\n" "Введите ID пользователя для проверки уровня:",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("admin_levels_menu"),
    )
    await state.set_state(AdminLevelsStates.waiting_for_user_id)
    await state.update_data(action="check")
    await callback.answer()


@router.callback_query(F.data == "admin_levels_spent")
async def admin_levels_spent(callback: types.CallbackQuery, state: FSMContext):
    """Изменение суммы потраченных монет"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "💰 **Изменение потраченных монет**\n\n"
        "Введите ID пользователя для изменения суммы потраченных монет:",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("admin_levels_menu"),
    )
    await state.set_state(AdminLevelsStates.waiting_for_user_id)
    await state.update_data(action="spent")
    await callback.answer()


@router.message(AdminLevelsStates.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    """Обработка введенного ID пользователя"""
    try:
        target_id = int(message.text.strip())
        data = await state.get_data()
        action = data.get("action")

        user = db.get_user(target_id)

        if not user:
            await message.answer(
                f"❌ Пользователь с ID {target_id} не найден!",
                reply_markup=get_back_keyboard("admin_levels_menu"),
            )
            await state.clear()
            return

        user_level = db.get_user_level(target_id)
        all_levels = db.get_all_levels()

        if action == "check":
            # Просто показываем информацию об уровне
            level_display = get_level_name_with_emoji(
                user_level["current_level"], user_level["level_name"]
            )

            text = (
                f"📊 **Информация об уровне пользователя**\n\n"
                f"👤 Пользователь: {user['first_name'] or user['username'] or 'Неизвестно'}\n"
                f"🆔 ID: `{target_id}`\n"
                f"🎚️ Текущий уровень: {level_display}\n"
                f"✨ Множитель удачи: x{user_level['luck_multiplier']}\n"
                f"💰 Потрачено на уровни: {format_number(user_level['total_spent'])} монет\n"
                f"📅 Последнее повышение: {user_level['upgraded_at'] or 'Никогда'}"
            )

            await message.answer(
                text,
                parse_mode="Markdown",
                reply_markup=get_back_keyboard("admin_levels_menu"),
            )
            await state.clear()

        elif action in ["upgrade", "downgrade", "reset"]:
            # Показываем список доступных уровней
            await state.update_data(target_id=target_id)

            if action == "upgrade":
                # Показываем уровни выше текущего
                available_levels = [
                    l for l in all_levels if l["number"] > user_level["current_level"]
                ]
                title = "⬆️ **Выберите новый уровень**"
            elif action == "downgrade":
                # Показываем уровни ниже текущего
                available_levels = [
                    l for l in all_levels if l["number"] < user_level["current_level"]
                ]
                title = "⬇️ **Выберите новый уровень**"
            else:  # reset
                # Просто устанавливаем уровень 1
                await state.update_data(new_level=1)
                # Сразу переходим к подтверждению
                await confirm_level_change(message, state, target_id, 1, "reset")
                return

            if not available_levels:
                await message.answer(
                    f"❌ Нет доступных уровней для {'повышения' if action == 'upgrade' else 'понижения'}",
                    reply_markup=get_back_keyboard("admin_levels_menu"),
                )
                await state.clear()
                return

            await message.answer(
                f"{title}\n\n"
                f"Текущий уровень пользователя: {user_level['level_name']}",
                parse_mode="Markdown",
                reply_markup=get_level_selection_keyboard(
                    available_levels, action, target_id
                ),
            )
            await state.set_state(AdminLevelsStates.waiting_for_new_level)

        elif action == "spent":
            # Запрашиваем новую сумму потраченных монет
            await state.update_data(target_id=target_id)
            await message.answer(
                f"💰 Введите новую сумму потраченных монет для пользователя {target_id}:\n"
                f"Текущая сумма: {format_number(user_level['total_spent'])} монет",
                reply_markup=get_back_keyboard("admin_levels_menu"),
            )
            await state.set_state(AdminLevelsStates.waiting_for_new_level)
            await state.update_data(spent_action=True)

    except ValueError:
        await message.answer(
            "❌ Введите корректный ID (число)!",
            reply_markup=get_back_keyboard("admin_levels_menu"),
        )
        await state.clear()


@router.callback_query(
    AdminLevelsStates.waiting_for_new_level, F.data.startswith("admin_level_select_")
)
async def process_level_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора уровня"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        action = parts[3]
        target_id = int(parts[4])
        new_level = int(parts[5])

        await state.update_data(target_id=target_id, new_level=new_level, action=action)

        user = db.get_user(target_id)
        user_level = db.get_user_level(target_id)
        new_level_info = db.get_level(new_level)

        action_names = {
            "upgrade": "повысить",
            "downgrade": "понизить",
            "reset": "сбросить",
        }

        await callback.message.edit_text(
            f"❓ **Подтверждение действия**\n\n"
            f"Вы хотите {action_names.get(action, 'изменить')} уровень пользователя\n"
            f"👤 {user['first_name'] or user['username'] or target_id} (ID: `{target_id}`)\n\n"
            f"**Текущий уровень:** {user_level['level_name']} (x{user_level['luck_multiplier']})\n"
            f"**Новый уровень:** {new_level_info['name']} (x{new_level_info['luck_multiplier']})\n\n"
            f"Подтвердите действие:",
            parse_mode="Markdown",
            reply_markup=get_confirm_keyboard(target_id, new_level, action),
        )

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    await callback.answer()


@router.callback_query(F.data.startswith("admin_level_confirm_"))
async def confirm_level_change(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение изменения уровня"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    try:
        parts = callback.data.split("_")
        target_id = int(parts[3])
        new_level = int(parts[4])
        action = parts[5]

        user = db.get_user(target_id)
        old_level_info = db.get_user_level(target_id)
        new_level_info = db.get_level(new_level)

        # Выполняем изменение уровня
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Получаем текущие данные
            cursor.execute(
                """
                SELECT current_level, total_spent FROM user_levels WHERE user_id = ?
            """,
                (target_id,),
            )
            row = cursor.fetchone()

            if not row:
                await callback.answer(
                    "❌ Пользователь не найден в таблице уровней", show_alert=True
                )
                return

            current_level, total_spent = row

            # Обновляем уровень
            cursor.execute(
                """
                UPDATE user_levels 
                SET current_level = ?, upgraded_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """,
                (new_level, target_id),
            )

            # Записываем транзакцию
            cursor.execute(
                """
                INSERT INTO transactions (user_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?)
            """,
                (
                    target_id,
                    0,
                    "admin_level_change",
                    f"Администратор {callback.from_user.id} изменил уровень с {current_level} на {new_level}",
                ),
            )

            conn.commit()

        # Уведомляем пользователя об изменении уровня
        try:
            level_display = get_level_name_with_emoji(new_level, new_level_info["name"])
            await callback.bot.send_message(
                target_id,
                f"🎚️ **Ваш уровень был изменен администратором!**\n\n"
                f"**Новый уровень:** {level_display}\n"
                f"**Новый множитель удачи:** x{new_level_info['luck_multiplier']}\n\n"
                f"Теперь ваша удача увеличилась! ✨",
            )
        except:
            pass

        action_names = {
            "upgrade": "повышен",
            "downgrade": "понижен",
            "reset": "сброшен",
        }

        await callback.message.edit_text(
            f"✅ **Уровень пользователя успешно {action_names.get(action, 'изменен')}!**\n\n"
            f"👤 Пользователь: {user['first_name'] or user['username'] or target_id}\n"
            f"🆔 ID: `{target_id}`\n"
            f"**Старый уровень:** {old_level_info['level_name']} (x{old_level_info['luck_multiplier']})\n"
            f"**Новый уровень:** {new_level_info['name']} (x{new_level_info['luck_multiplier']})",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard("admin_levels_menu"),
        )

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    await state.clear()
    await callback.answer()


@router.message(AdminLevelsStates.waiting_for_new_level)
async def process_spent_amount(message: types.Message, state: FSMContext):
    """Обработка новой суммы потраченных монет"""
    try:
        amount = int(message.text)
        data = await state.get_data()
        target_id = data.get("target_id")
        spent_action = data.get("spent_action")

        if not spent_action:
            await state.clear()
            return

        if amount < 0:
            await message.answer(
                "❌ Сумма не может быть отрицательной!",
                reply_markup=get_back_keyboard("admin_levels_menu"),
            )
            return

        user = db.get_user(target_id)
        old_level_info = db.get_user_level(target_id)

        # Обновляем сумму потраченных монет
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE user_levels 
                SET total_spent = ?
                WHERE user_id = ?
            """,
                (amount, target_id),
            )
            conn.commit()

        # Получаем новый уровень (может измениться из-за суммы)
        new_level_info = db.get_user_level(target_id)

        await message.answer(
            f"✅ **Сумма потраченных монет обновлена!**\n\n"
            f"👤 Пользователь: {user['first_name'] or user['username'] or target_id}\n"
            f"🆔 ID: `{target_id}`\n"
            f"**Старая сумма:** {format_number(old_level_info['total_spent'])} монет\n"
            f"**Новая сумма:** {format_number(amount)} монет\n"
            f"**Текущий уровень:** {new_level_info['level_name']}\n"
            f"**Множитель удачи:** x{new_level_info['luck_multiplier']}",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard("admin_levels_menu"),
        )

    except ValueError:
        await message.answer(
            "❌ Введите число!", reply_markup=get_back_keyboard("admin_levels_menu")
        )
    finally:
        await state.clear()


@router.callback_query(F.data == "admin_levels_menu")
async def back_to_levels_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в меню управления уровнями"""
    await state.clear()
    await admin_levels_menu(callback)
