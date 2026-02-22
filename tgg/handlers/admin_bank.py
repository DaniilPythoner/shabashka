# handlers/admin_bank.py
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS
from database import db
from utils import format_number

router = Router()

def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    if user_id in ADMIN_IDS:
        return True
    user = db.get_user(user_id)
    return user and user.get("is_admin", False)

@router.callback_query(F.data.startswith("admin_confirm_bank_"))
async def admin_confirm_bank(callback: types.CallbackQuery):
    """Подтверждение банковского платежа администратором"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    deposit_id = int(callback.data.split("_")[3])
    
    if db.confirm_bank_deposit(deposit_id, callback.from_user.id):
        deposit = db.get_bank_deposit(deposit_id)
        user = db.get_user(deposit['user_id'])
        
        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                deposit['user_id'],
                f"✅ **Банковское пополнение подтверждено!**\n\n"
                f"Сумма: {deposit['amount']} руб.\n"
                f"💰 Начислено: +{deposit['coins']} монет\n"
                f"Новый баланс: {format_number(user['balance'])} монет\n\n"
                f"Спасибо за использование бота!",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка уведомления пользователя: {e}")
        
        await callback.message.edit_caption(
            caption=f"✅ **Банковский платеж подтвержден!**\n\n"
                    f"Заявка #{deposit_id}\n"
                    f"Сумма: {deposit['amount']} руб.\n"
                    f"Монеты: +{deposit['coins']}\n"
                    f"Администратор: @{callback.from_user.username or 'админ'}\n"
                    f"Дата: {deposit['completed_at'][:19] if deposit['completed_at'] else 'сейчас'}",
            parse_mode="Markdown",
            reply_markup=None
        )
        
        await callback.answer("✅ Платеж подтвержден!", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при подтверждении", show_alert=True)

@router.callback_query(F.data.startswith("admin_reject_bank_"))
async def admin_reject_bank(callback: types.CallbackQuery):
    """Отклонение банковского платежа администратором"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    deposit_id = int(callback.data.split("_")[3])
    
    if db.reject_bank_deposit(deposit_id, callback.from_user.id):
        deposit = db.get_bank_deposit(deposit_id)
        
        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                deposit['user_id'],
                f"❌ **Банковское пополнение отклонено**\n\n"
                f"Сумма: {deposit['amount']} руб.\n\n"
                f"Причина: платеж не прошел проверку.\n"
                f"Возможно, скриншот не читается или код платежа указан неверно.\n\n"
                f"Свяжитесь с поддержкой для уточнения.",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка уведомления пользователя: {e}")
        
        await callback.message.edit_caption(
            caption=f"❌ **Банковский платеж отклонен**\n\n"
                    f"Заявка #{deposit_id}\n"
                    f"Сумма: {deposit['amount']} руб.\n"
                    f"Администратор: @{callback.from_user.username or 'админ'}\n"
                    f"Дата: {deposit['completed_at'][:19] if deposit['completed_at'] else 'сейчас'}",
            parse_mode="Markdown",
            reply_markup=None
        )
        
        await callback.answer("✅ Платеж отклонен", show_alert=True)
    else:
        await callback.answer("❌ Ошибка при отклонении", show_alert=True)

@router.callback_query(F.data == "admin_pending_bank")
async def admin_pending_bank(callback: types.CallbackQuery):
    """Список ожидающих банковских платежей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    deposits = db.get_pending_bank_deposits()
    
    if not deposits:
        await callback.message.edit_text(
            "📭 Нет ожидающих банковских пополнений",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_payments_menu")]
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
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_payments_menu")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    await callback.answer()