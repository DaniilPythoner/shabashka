# handlers/http_bind.py
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, RUB_TO_COINS
from database import db
from utils import format_number

router = Router()


class HTTPBindStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_donation_id = State()


@router.callback_query(F.data.startswith("admin_confirm_da_"))
async def admin_confirm_da_payment(callback: types.CallbackQuery):
    """Подтверждение платежа администратором"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    donation_id = callback.data.split("_")[3]

    payment = db.get_http_payment(donation_id)
    if not payment:
        await callback.answer("❌ Платеж не найден", show_alert=True)
        return

    if payment["status"] != "pending":
        await callback.answer("❌ Платеж уже обработан", show_alert=True)
        return

    # Запрашиваем ID пользователя
    await callback.message.edit_text(
        f"🔗 Введите ID пользователя Telegram для начисления монет за донат `{donation_id}`:\n\n"
        f"Сумма доната: {payment['amount']} руб.\n"
        f"Монет к начислению: {payment['coins']}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отмена", callback_data="admin_pending_http_payments"
                    )
                ]
            ]
        ),
    )

    # Сохраняем donation_id в состоянии
    await callback.state.update_data(donation_id=donation_id)
    await callback.state.set_state(HTTPBindStates.waiting_for_user_id)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_reject_da_"))
async def admin_reject_da_payment(callback: types.CallbackQuery):
    """Отклонение платежа администратором"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    donation_id = callback.data.split("_")[3]

    payment = db.get_http_payment(donation_id)
    if not payment:
        await callback.answer("❌ Платеж не найден", show_alert=True)
        return

    if payment["status"] != "pending":
        await callback.answer("❌ Платеж уже обработан", show_alert=True)
        return

    # Отклоняем платеж
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE da_http_payments 
            SET status = 'rejected', processed_at = CURRENT_TIMESTAMP, admin_id = ?
            WHERE donation_id = ?
        """,
            (callback.from_user.id, donation_id),
        )
        conn.commit()

    await callback.message.edit_text(
        f"❌ Платеж `{donation_id}` отклонен",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_pending_http_payments"
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_bind_da_"))
async def admin_bind_da_payment(callback: types.CallbackQuery, state: FSMContext):
    """Привязка платежа к пользователю"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    donation_id = callback.data.split("_")[3]

    payment = db.get_http_payment(donation_id)
    if not payment:
        await callback.answer("❌ Платеж не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"🔗 Введите ID пользователя Telegram для привязки доната `{donation_id}`:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отмена", callback_data="admin_pending_http_payments"
                    )
                ]
            ]
        ),
    )

    await state.update_data(donation_id=donation_id)
    await state.set_state(HTTPBindStates.waiting_for_user_id)
    await callback.answer()


@router.message(HTTPBindStates.waiting_for_user_id)
async def process_bind_user_id(message: types.Message, state: FSMContext):
    """Обработка введенного ID пользователя для привязки"""
    try:
        user_id = int(message.text.strip())
        data = await state.get_data()
        donation_id = data.get("donation_id")

        # Получаем информацию о донате
        payment = db.get_http_payment(donation_id)
        if not payment:
            await message.answer("❌ Донат не найден")
            await state.clear()
            return

        if payment["status"] != "pending":
            await message.answer("❌ Этот донат уже обработан")
            await state.clear()
            return

        # Проверяем существование пользователя
        user = db.get_user(user_id)
        if not user:
            await message.answer(
                f"❌ Пользователь с ID {user_id} не найден!\n"
                f"Убедитесь, что пользователь запускал бота хотя бы раз.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="❌ Отмена",
                                callback_data="admin_pending_http_payments",
                            )
                        ]
                    ]
                ),
            )
            return

        # Подтверждаем платеж и начисляем монеты
        if db.confirm_http_payment(donation_id, message.from_user.id, user_id):
            # Получаем обновленный баланс
            updated_user = db.get_user(user_id)

            await message.answer(
                f"✅ Донат успешно привязан!\n\n"
                f"👤 Пользователь: {user['first_name'] or user_id}\n"
                f"💰 Сумма доната: {payment['amount']} руб.\n"
                f"🎁 Начислено: +{payment['coins']} монет\n"
                f"Новый баланс: {format_number(updated_user['balance'])} монет\n"
                f"🆔 ID доната: `{donation_id}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🔙 К списку платежей",
                                callback_data="admin_pending_http_payments",
                            )
                        ]
                    ]
                ),
            )

            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    user_id,
                    f"✅ **Вам начислены монеты!**\n\n"
                    f"Вы получили **+{payment['coins']}** монет за донат через DonationAlerts!\n"
                    f"Сумма доната: {payment['amount']} руб.\n"
                    f"Сообщение: {payment['message'] or '—'}\n\n"
                    f"Спасибо за поддержку! 🎲",
                    parse_mode="Markdown",
                )
            except Exception as e:
                await message.answer(f"⚠️ Не удалось уведомить пользователя: {e}")
        else:
            await message.answer("❌ Ошибка при подтверждении платежа")

        await state.clear()

    except ValueError:
        await message.answer("❌ Введите корректный ID (число)!")


@router.callback_query(F.data.startswith("http_bind_"))
async def http_bind_donation(callback: types.CallbackQuery, state: FSMContext):
    """Привязка доната к пользователю (из уведомления)"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    donation_id = callback.data.split("_")[2]

    payment = db.get_http_payment(donation_id)
    if not payment:
        await callback.answer("❌ Донат не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"🔗 Введите ID пользователя Telegram для привязки доната `{donation_id}`:\n\n"
        f"Сумма: {payment['amount']} руб.\n"
        f"Монет: {payment['coins']}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Отмена", callback_data="admin_pending_http_payments"
                    )
                ]
            ]
        ),
    )

    await state.update_data(donation_id=donation_id)
    await state.set_state(HTTPBindStates.waiting_for_user_id)
    await callback.answer()


@router.callback_query(F.data.startswith("http_confirm_"))
async def http_confirm_without_user(callback: types.CallbackQuery):
    """Подтверждение доната без привязки к пользователю"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    donation_id = callback.data.split("_")[2]

    payment = db.get_http_payment(donation_id)
    if not payment:
        await callback.answer("❌ Донат не найден", show_alert=True)
        return

    if payment["status"] != "pending":
        await callback.answer("❌ Донат уже обработан", show_alert=True)
        return

    # Обновляем статус (без начисления)
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE da_http_payments 
            SET status = 'completed', processed_at = CURRENT_TIMESTAMP, admin_id = ?
            WHERE donation_id = ?
        """,
            (callback.from_user.id, donation_id),
        )
        conn.commit()

    await callback.message.edit_text(
        f"✅ Донат `{donation_id}` отмечен как обработанный (без начисления)\n"
        f"Сумма: {payment['amount']} руб.\n"
        f"Отправитель: {payment['username']}",
        parse_mode="Markdown",
    )

    await callback.answer()


@router.callback_query(F.data == "http_cancel_bind")
async def http_cancel_bind(callback: types.CallbackQuery, state: FSMContext):
    """Отмена привязки"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Привязка отменена",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_pending_http_payments"
                    )
                ]
            ]
        ),
    )
    await callback.answer()
