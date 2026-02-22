# handlers/admin_donation.py
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS
from database import db
from utils import format_number

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id in ADMIN_IDS or (db.get_user(user_id) or {}).get("is_admin", False)


@router.callback_query(F.data.startswith("admin_confirm_da_"))
async def admin_confirm_da_payment(callback: types.CallbackQuery):
    """Подтверждение платежа администратором"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    payment_id = callback.data.split("_")[3]

    if db.confirm_da_manual_payment(payment_id, callback.from_user.id):
        payment = db.get_da_manual_payment(payment_id)
        user = db.get_user(payment["user_id"])

        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                payment["user_id"],
                f"✅ **Пополнение подтверждено!**\n\n"
                f"Сумма: {payment['amount']} руб.\n"
                f"💰 Начислено: +{payment['coins']} монет\n"
                f"Новый баланс: {format_number(user['balance'])} монет\n\n"
                f"Спасибо за использование бота!",
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"Ошибка уведомления пользователя: {e}")

        await callback.message.edit_caption(
            caption=f"✅ **Платеж подтвержден!**\n\n"
            f"ID: `{payment_id}`\n"
            f"Сумма: {payment['amount']} руб.\n"
            f"Монеты: +{payment['coins']}\n"
            f"Администратор: @{callback.from_user.username or 'админ'}\n"
            f"Дата: {payment['completed_at'][:19] if payment['completed_at'] else 'сейчас'}",
            parse_mode="Markdown",
            reply_markup=None,
        )

        await callback.answer("✅ Платеж подтвержден!", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при подтверждении", show_alert=True)


@router.callback_query(F.data.startswith("admin_reject_da_"))
async def admin_reject_da_payment(callback: types.CallbackQuery):
    """Отклонение платежа администратором"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    payment_id = callback.data.split("_")[3]

    if db.reject_da_manual_payment(payment_id, callback.from_user.id):
        payment = db.get_da_manual_payment(payment_id)

        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                payment["user_id"],
                f"❌ **Пополнение отклонено**\n\n"
                f"Сумма: {payment['amount']} руб.\n\n"
                f"Причина: платеж не прошел проверку.\n"
                f"Возможно, скриншот не читается или платеж не был завершен.\n\n"
                f"Свяжитесь с поддержкой для уточнения.",
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"Ошибка уведомления пользователя: {e}")

        await callback.message.edit_caption(
            caption=f"❌ **Платеж отклонен**\n\n"
            f"ID: `{payment_id}`\n"
            f"Сумма: {payment['amount']} руб.\n"
            f"Администратор: @{callback.from_user.username or 'админ'}\n"
            f"Дата: {payment['completed_at'][:19] if payment['completed_at'] else 'сейчас'}",
            parse_mode="Markdown",
            reply_markup=None,
        )

        await callback.answer("✅ Платеж отклонен", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при отклонении", show_alert=True)


@router.callback_query(F.data == "admin_pending_da")
async def admin_pending_da_payments(callback: types.CallbackQuery):
    """Список ожидающих платежей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return

    payments = db.get_pending_da_manual_payments()

    if not payments:
        await callback.message.edit_text(
            "📭 Нет ожидающих платежей DonationAlerts",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="admin_payments_menu"
                        )
                    ]
                ]
            ),
        )
        await callback.answer()
        return

    text = "📋 **Ожидающие платежи DonationAlerts**\n\n"

    for p in payments[:10]:
        user = db.get_user(p["user_id"])
        username = (
            f"@{user['username']}"
            if user and user["username"]
            else f"ID {p['user_id']}"
        )

        text += f"🆔 `{p['payment_id']}`\n"
        text += f"👤 {username}\n"
        text += f"💰 {p['amount']} руб. = {p['coins']} монет\n"
        text += f"📅 {p['created_at'][:16]}\n"
        text += f"🔍 /check_da_{p['payment_id']}\n\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить", callback_data="admin_pending_da"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="admin_payments_menu"
                )
            ],
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


@router.message(lambda message: message.text and message.text.startswith("/check_da_"))
async def check_da_payment_command(message: types.Message):
    """Команда для проверки конкретного платежа"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора!")
        return

    payment_id = message.text.replace("/check_da_", "").strip()
    payment = db.get_da_manual_payment(payment_id)

    if not payment:
        await message.answer(f"❌ Платеж с ID {payment_id} не найден")
        return

    user = db.get_user(payment["user_id"])

    text = (
        f"📊 **Информация о платеже**\n\n"
        f"ID: `{payment_id}`\n"
        f"Статус: {payment['status']}\n"
        f"Сумма: {payment['amount']} руб.\n"
        f"Монеты: {payment['coins']}\n\n"
        f"👤 **Пользователь:**\n"
        f"ID: {payment['user_id']}\n"
        f"Username: @{user['username'] or 'нет'}\n"
        f"Имя: {user['first_name'] or 'нет'}\n"
        f"Баланс: {format_number(user['balance'])} монет\n\n"
        f"📅 Создан: {payment['created_at'][:19]}"
    )

    if payment["screenshot_id"]:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить",
                        callback_data=f"admin_confirm_da_{payment_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Отклонить",
                        callback_data=f"admin_reject_da_{payment_id}",
                    ),
                ]
            ]
        )

        await message.answer_photo(
            photo=payment["screenshot_id"],
            caption=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    else:
        text += "\n\n⚠️ Скриншот отсутствует!"
        await message.answer(text, parse_mode="Markdown")
