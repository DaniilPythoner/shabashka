# handlers/admin_luck.py
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


# Состояния для FSM
class AdminLuckStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_luck_value = State()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    if user_id in ADMIN_IDS:
        return True
    user = db.get_user(user_id)
    return user and user.get("is_admin", False)


def get_admin_luck_keyboard():
    """Клавиатура управления удачей"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="👁 Просмотреть удачу", callback_data="admin_luck_view"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(
            text="⬆️ Увеличить удачу", callback_data="admin_luck_increase"
        ),
        InlineKeyboardButton(
            text="⬇️ Уменьшить удачу", callback_data="admin_luck_decrease"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(
            text="⚡ Установить значение", callback_data="admin_luck_set"
        ),
        InlineKeyboardButton(
            text="🔄 Сбросить удачу", callback_data="admin_luck_reset"
        ),
        width=2,
    )
    builder.row(
        InlineKeyboardButton(text="📊 Топ по удаче", callback_data="admin_luck_top"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"), width=1
    )

    return builder.as_markup()


def get_luck_value_keyboard():
    """Клавиатура для выбора значения удачи"""
    builder = InlineKeyboardBuilder()

    values = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0, 1.2, 1.5, 1.8, 2.0, 2.5, 3.0]

    buttons = []
    for val in values:
        buttons.append(
            InlineKeyboardButton(
                text=f"x{val}", callback_data=f"admin_luck_value_{val}"
            )
        )

    # Располагаем по 3 в ряд
    for i in range(0, len(buttons), 3):
        builder.row(*buttons[i : i + 3])

    builder.row(
        InlineKeyboardButton(text="✏️ Своё значение", callback_data="admin_luck_custom"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_luck_menu"), width=1
    )

    return builder.as_markup()


def get_back_keyboard(callback: str):
    """Клавиатура с кнопкой назад"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=callback), width=1)
    return builder.as_markup()


@router.message(Command("admin_luck"))
async def cmd_admin_luck(message: types.Message):
    """Команда для открытия меню управления удачей"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора!")
        return

    await message.answer(
        "⚡ **Управление удачей пользователей**\n\n"
        "Здесь вы можете изменять множитель удачи для конкретных пользователей.\n"
        "Значение от 0.1 (минимальная удача) до 3.0 (максимальная удача).\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_luck_keyboard(),
    )


@router.callback_query(F.data == "admin_luck_menu")
async def admin_luck_menu(callback: types.CallbackQuery):
    """Меню управления удачей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "⚡ **Управление удачей пользователей**\n\n"
        "Значение от 0.1 (минимальная удача) до 3.0 (максимальная удача).\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_luck_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_luck_view")
async def admin_luck_view(callback: types.CallbackQuery, state: FSMContext):
    """Просмотр удачи пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "👁 Введите ID пользователя для просмотра удачи:",
        reply_markup=get_back_keyboard("admin_luck_menu"),
    )
    await state.set_state(AdminLuckStates.waiting_for_user_id)
    await state.update_data(action="view")
    await callback.answer()


@router.callback_query(F.data == "admin_luck_increase")
async def admin_luck_increase(callback: types.CallbackQuery, state: FSMContext):
    """Увеличение удачи пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "⬆️ Введите ID пользователя для увеличения удачи:",
        reply_markup=get_back_keyboard("admin_luck_menu"),
    )
    await state.set_state(AdminLuckStates.waiting_for_user_id)
    await state.update_data(action="increase")
    await callback.answer()


@router.callback_query(F.data == "admin_luck_decrease")
async def admin_luck_decrease(callback: types.CallbackQuery, state: FSMContext):
    """Уменьшение удачи пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "⬇️ Введите ID пользователя для уменьшения удачи:",
        reply_markup=get_back_keyboard("admin_luck_menu"),
    )
    await state.set_state(AdminLuckStates.waiting_for_user_id)
    await state.update_data(action="decrease")
    await callback.answer()


@router.callback_query(F.data == "admin_luck_set")
async def admin_luck_set(callback: types.CallbackQuery, state: FSMContext):
    """Установка конкретного значения удачи"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "⚡ Введите ID пользователя для установки значения удачи:",
        reply_markup=get_back_keyboard("admin_luck_menu"),
    )
    await state.set_state(AdminLuckStates.waiting_for_user_id)
    await state.update_data(action="set")
    await callback.answer()


@router.callback_query(F.data == "admin_luck_reset")
async def admin_luck_reset(callback: types.CallbackQuery, state: FSMContext):
    """Сброс удачи пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    await callback.message.edit_text(
        "🔄 Введите ID пользователя для сброса удачи (к 1.0):",
        reply_markup=get_back_keyboard("admin_luck_menu"),
    )
    await state.set_state(AdminLuckStates.waiting_for_user_id)
    await state.update_data(action="reset")
    await callback.answer()


@router.callback_query(F.data == "admin_luck_top")
async def admin_luck_top(callback: types.CallbackQuery):
    """Топ пользователей по удаче"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    # Получаем всех пользователей с нестандартной удачей
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, username, first_name, custom_luck 
            FROM users 
            WHERE custom_luck IS NOT NULL AND custom_luck != 1.0
            ORDER BY custom_luck DESC
            LIMIT 20
        """
        )
        rows = cursor.fetchall()

    if not rows:
        await callback.message.edit_text(
            "📊 **Топ по удаче**\n\n" "Нет пользователей с измененной удачей",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard("admin_luck_menu"),
        )
        await callback.answer()
        return

    text = "📊 **Топ пользователей по удаче**\n\n"

    for i, row in enumerate(rows, 1):
        user_id, username, first_name, custom_luck = row
        name = first_name or username or f"ID {user_id}"

        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} **{name}**\n"
        text += f"   ├ ID: `{user_id}`\n"
        text += f"   └ Удача: x{custom_luck:.2f}\n\n"

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard("admin_luck_menu")
    )
    await callback.answer()


@router.message(AdminLuckStates.waiting_for_user_id)
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
                reply_markup=get_back_keyboard("admin_luck_menu"),
            )
            await state.clear()
            return

        current_luck = db.get_user_custom_luck(target_id)

        if action == "view":
            # Просто показываем текущую удачу
            await message.answer(
                f"📊 **Информация об удаче**\n\n"
                f"👤 Пользователь: {user['first_name'] or user['username'] or 'Неизвестно'}\n"
                f"🆔 ID: `{target_id}`\n"
                f"⚡ Текущая удача: x{current_luck:.2f}\n"
                f"📊 Уровень: {db.get_user_level(target_id)['level_name']}",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard("admin_luck_menu"),
            )
            await state.clear()

        elif action in ["increase", "decrease"]:
            # Увеличиваем или уменьшаем удачу на 0.1
            new_luck = current_luck
            if action == "increase":
                new_luck = min(3.0, current_luck + 0.1)
            else:
                new_luck = max(0.1, current_luck - 0.1)

            if new_luck == current_luck:
                await message.answer(
                    f"❌ Невозможно {'увеличить' if action == 'increase' else 'уменьшить'} удачу. "
                    f"{'Максимальное' if action == 'increase' else 'Минимальное'} значение уже достигнуто.",
                    reply_markup=get_back_keyboard("admin_luck_menu"),
                )
            else:
                db.set_user_custom_luck(target_id, new_luck)
                await message.answer(
                    f"✅ Удача пользователя {'увеличена' if action == 'increase' else 'уменьшена'}!\n\n"
                    f"👤 Пользователь: {user['first_name'] or user['username'] or target_id}\n"
                    f"🆔 ID: `{target_id}`\n"
                    f"⚡ Старая удача: x{current_luck:.2f}\n"
                    f"⚡ Новая удача: x{new_luck:.2f}",
                    parse_mode="Markdown",
                    reply_markup=get_back_keyboard("admin_luck_menu"),
                )

                # Уведомляем пользователя
                try:
                    await message.bot.send_message(
                        target_id,
                        f"⚡ **Ваша удача была изменена администратором!**\n\n"
                        f"**Новое значение:** x{new_luck:.2f}\n"
                        f"**Предыдущее:** x{current_luck:.2f}",
                        parse_mode="Markdown",
                    )
                except:
                    pass

            await state.clear()

        elif action == "reset":
            # Сбрасываем удачу к 1.0
            db.reset_user_custom_luck(target_id)
            await message.answer(
                f"✅ Удача пользователя сброшена!\n\n"
                f"👤 Пользователь: {user['first_name'] or user['username'] or target_id}\n"
                f"🆔 ID: `{target_id}`\n"
                f"⚡ Новая удача: x1.0",
                parse_mode="Markdown",
                reply_markup=get_back_keyboard("admin_luck_menu"),
            )

            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    target_id,
                    f"🔄 **Ваша удача была сброшена администратором!**\n\n"
                    f"**Новое значение:** x1.0",
                    parse_mode="Markdown",
                )
            except:
                pass

            await state.clear()

        elif action == "set":
            # Переходим к выбору значения
            await state.update_data(target_id=target_id)
            await message.answer(
                f"⚡ Выберите значение удачи для пользователя {target_id}:\n"
                f"Текущее значение: x{current_luck:.2f}",
                reply_markup=get_luck_value_keyboard(),
            )
            await state.set_state(AdminLuckStates.waiting_for_luck_value)

    except ValueError:
        await message.answer(
            "❌ Введите корректный ID (число)!",
            reply_markup=get_back_keyboard("admin_luck_menu"),
        )
        await state.clear()


@router.callback_query(
    AdminLuckStates.waiting_for_luck_value, F.data.startswith("admin_luck_value_")
)
async def process_luck_value(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбранного значения удачи"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    try:
        luck_value = float(callback.data.split("_")[3])
        data = await state.get_data()
        target_id = data.get("target_id")

        user = db.get_user(target_id)
        old_luck = db.get_user_custom_luck(target_id)

        db.set_user_custom_luck(target_id, luck_value)

        await callback.message.edit_text(
            f"✅ Удача пользователя изменена!\n\n"
            f"👤 Пользователь: {user['first_name'] or user['username'] or target_id}\n"
            f"🆔 ID: `{target_id}`\n"
            f"⚡ Старая удача: x{old_luck:.2f}\n"
            f"⚡ Новая удача: x{luck_value:.2f}",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard("admin_luck_menu"),
        )

        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                target_id,
                f"⚡ **Ваша удача была изменена администратором!**\n\n"
                f"**Новое значение:** x{luck_value:.2f}\n"
                f"**Предыдущее:** x{old_luck:.2f}",
                parse_mode="Markdown",
            )
        except:
            pass

    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
    finally:
        await state.clear()
        await callback.answer()


@router.callback_query(
    AdminLuckStates.waiting_for_luck_value, F.data == "admin_luck_custom"
)
async def custom_luck_value(callback: types.CallbackQuery, state: FSMContext):
    """Ввод своего значения удачи"""
    await callback.message.edit_text(
        "✏️ Введите значение удачи (от 0.1 до 3.0, например: 1.5):",
        reply_markup=get_back_keyboard("admin_luck_menu"),
    )
    # Оставляем состояние waiting_for_luck_value, но теперь будем ждать текст
    await callback.answer()


@router.message(AdminLuckStates.waiting_for_luck_value)
async def process_custom_luck_value(message: types.Message, state: FSMContext):
    """Обработка своего значения удачи"""
    try:
        luck_value = float(message.text.replace(",", "."))

        if luck_value < 0.1 or luck_value > 3.0:
            await message.answer(
                "❌ Значение должно быть от 0.1 до 3.0!",
                reply_markup=get_back_keyboard("admin_luck_menu"),
            )
            return

        data = await state.get_data()
        target_id = data.get("target_id")

        user = db.get_user(target_id)
        old_luck = db.get_user_custom_luck(target_id)

        db.set_user_custom_luck(target_id, luck_value)

        await message.answer(
            f"✅ Удача пользователя изменена!\n\n"
            f"👤 Пользователь: {user['first_name'] or user['username'] or target_id}\n"
            f"🆔 ID: `{target_id}`\n"
            f"⚡ Старая удача: x{old_luck:.2f}\n"
            f"⚡ Новая удача: x{luck_value:.2f}",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard("admin_luck_menu"),
        )

        # Уведомляем пользователя
        try:
            await message.bot.send_message(
                target_id,
                f"⚡ **Ваша удача была изменена администратором!**\n\n"
                f"**Новое значение:** x{luck_value:.2f}\n"
                f"**Предыдущее:** x{old_luck:.2f}",
                parse_mode="Markdown",
            )
        except:
            pass

    except ValueError:
        await message.answer(
            "❌ Введите корректное число!",
            reply_markup=get_back_keyboard("admin_luck_menu"),
        )
    finally:
        await state.clear()
