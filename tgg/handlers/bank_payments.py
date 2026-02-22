# handlers/bank_payments.py
import datetime
import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    BANK_NAME, BANK_CARD,
    RUB_TO_COINS, MIN_BANK_DEPOSIT, ADMIN_IDS, SUPPORT_CONTACT,
    PAYMENT_EXPIRY_HOURS
)
from database import db
from utils import format_number, format_time_ago
from keyboards import get_back_keyboard

logger = logging.getLogger(__name__)

router = Router()

class BankPaymentStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_custom_amount = State()
    waiting_for_receipt_photo = State()

def get_bank_deposit_keyboard():
    """Клавиатура для банковского пополнения"""
    builder = InlineKeyboardBuilder()
    
    amounts = [500, 1000, 2000, 5000, 10000, 20000]
    
    for amount in amounts:
        coins = amount * RUB_TO_COINS
        builder.row(
            InlineKeyboardButton(
                text=f"💰 {amount} руб. = {coins} монет",
                callback_data=f"bank_amount_{amount}"
            ),
            width=1
        )
    
    builder.row(
        InlineKeyboardButton(text="✏️ Другая сумма", callback_data="bank_custom"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📋 История пополнений", callback_data="bank_history"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="wallet_menu"),
        width=2
    )
    
    return builder.as_markup()

def get_deposit_confirmation_keyboard(deposit_id: int):
    """Клавиатура подтверждения оплаты"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"bank_confirm_{deposit_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📋 История пополнений", callback_data="bank_history"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="bank_deposit"),
        width=2
    )
    
    return builder.as_markup()

def get_payment_status_keyboard(deposit_id: int):
    """Клавиатура для проверки статуса платежа"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔄 Проверить статус", callback_data=f"bank_check_{deposit_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="bank_deposit"),
        width=1
    )
    
    return builder.as_markup()

def get_bank_info_text() -> str:
    """Получение текста с информацией о банковском переводе"""
    return (
        "🏦 **Пополнение через банковский перевод**\n\n"
        "**Как пополнить:**\n"
        "1. Выберите сумму пополнения\n"
        "2. Получите уникальный код платежа\n"
        "3. Переведите деньги на карту с указанием кода\n"
        "4. Пришлите фото чека\n"
        "5. Администратор проверит и начислит монеты\n\n"
        f"**Курс:** 1 рубль = {RUB_TO_COINS} монет\n"
        f"**Минимальная сумма:** {MIN_BANK_DEPOSIT} руб.\n"
        f"**Срок действия заявки:** {PAYMENT_EXPIRY_HOURS} ч.\n\n"
        "**Реквизиты для перевода:**\n"
        f"🏦 Банк: {BANK_NAME}\n"
        f"💳 Карта: `{BANK_CARD}`\n"
    )

@router.callback_query(F.data == "bank_deposit")
async def bank_deposit(callback: types.CallbackQuery):
    """Начало процесса банковского пополнения"""
    await callback.message.edit_text(
        get_bank_info_text(),
        parse_mode="Markdown",
        reply_markup=get_bank_deposit_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("bank_amount_"))
async def process_bank_amount(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбранной суммы"""
    amount = int(callback.data.split("_")[2])
    
    user_id = callback.from_user.id
    deposit = db.create_bank_deposit(user_id, amount)
    
    # Сохраняем ID депозита в состояние
    await state.update_data(deposit_id=deposit["id"])
    
    expires = datetime.datetime.fromisoformat(deposit["expires_at"]).strftime("%d.%m.%Y %H:%M")
    
    text = (
        f"💰 **Заявка на пополнение создана!**\n\n"
        f"Сумма: **{amount} руб.**\n"
        f"К начислению: **{deposit['coins']}** монет\n"
        f"Код платежа: `{deposit['code']}`\n"
        f"Срок действия: до {expires}\n\n"
        f"**Реквизиты для перевода:**\n"
        f"🏦 Банк: {BANK_NAME}\n"
        f"💳 Карта: `{BANK_CARD}`\n"
        f"**Инструкция:**\n"
        f"1. Переведите **ровно {amount} руб.** на указанную карту\n"
        f"2. В комментарии к переводу ОБЯЗАТЕЛЬНО укажите код: `{deposit['code']}`\n"
        f"3. После оплаты нажмите кнопку «Я оплатил»\n"
        f"4. Приложите скриншот/фото чека\n\n"
        f"⚠️ Средства поступят после проверки администратором"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_deposit_confirmation_keyboard(deposit["id"])
    )
    await callback.answer()

@router.callback_query(F.data == "bank_custom")
async def bank_custom_amount(callback: types.CallbackQuery, state: FSMContext):
    """Ввод своей суммы"""
    await callback.message.edit_text(
        f"💰 Введите сумму пополнения в рублях (мин. {MIN_BANK_DEPOSIT}):",
        reply_markup=get_back_keyboard("bank_deposit")
    )
    await state.set_state(BankPaymentStates.waiting_for_custom_amount)
    await callback.answer()

@router.message(BankPaymentStates.waiting_for_custom_amount)
async def process_custom_bank_amount(message: types.Message, state: FSMContext):
    """Обработка своей суммы"""
    try:
        amount = int(message.text)
        
        if amount < MIN_BANK_DEPOSIT:
            await message.answer(
                f"❌ Минимальная сумма: {MIN_BANK_DEPOSIT} руб.",
                reply_markup=get_back_keyboard("bank_deposit")
            )
            return
        
        if amount > 1000000:
            await message.answer(
                "❌ Максимальная сумма: 1 000 000 руб.",
                reply_markup=get_back_keyboard("bank_deposit")
            )
            return
        
        user_id = message.from_user.id
        deposit = db.create_bank_deposit(user_id, amount)
        
        await state.update_data(deposit_id=deposit["id"])
        
        expires = datetime.datetime.fromisoformat(deposit["expires_at"]).strftime("%d.%m.%Y %H:%M")
        
        text = (
            f"💰 **Заявка на пополнение создана!**\n\n"
            f"Сумма: **{amount} руб.**\n"
            f"К начислению: **{deposit['coins']}** монет\n"
            f"Код платежа: `{deposit['code']}`\n"
            f"Срок действия: до {expires}\n\n"
            f"**Реквизиты для перевода:**\n"
            f"🏦 Банк: {BANK_NAME}\n"
            f"💳 Карта: `{BANK_CARD}`\n"
            f"**Инструкция:**\n"
            f"1. Переведите **ровно {amount} руб.** на указанную карту\n"
            f"2. В комментарии к переводу укажите код: `{deposit['code']}`\n"
            f"3. После оплаты нажмите кнопку «Я оплатил»"
        )
        
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_deposit_confirmation_keyboard(deposit["id"])
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Введите число!",
            reply_markup=get_back_keyboard("bank_deposit")
        )

@router.callback_query(F.data.startswith("bank_confirm_"))
async def bank_confirm_deposit(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение оплаты и запрос фото чека"""
    deposit_id = int(callback.data.split("_")[2])
    deposit = db.get_bank_deposit(deposit_id)
    
    if not deposit or deposit["status"] != "pending":
        await callback.answer("❌ Заявка не найдена или уже обработана", show_alert=True)
        return
    
    # Проверяем, не истек ли срок
    expires = datetime.datetime.fromisoformat(deposit["expires_at"])
    if datetime.datetime.now() > expires:
        db.reject_bank_deposit(deposit_id, 0)
        await callback.message.edit_text(
            "❌ Срок действия заявки истек. Создайте новую заявку.",
            reply_markup=get_back_keyboard("bank_deposit")
        )
        await callback.answer()
        return
    
    await state.update_data(deposit_id=deposit_id)
    
    await callback.message.edit_text(
        "📸 **Отправьте фото или скриншот чека об оплате**\n\n"
        "Убедитесь, что на фото виден:\n"
        "• Код платежа\n"
        "• Сумма перевода\n"
        "• Дата перевода\n"
        "• Статус \"Исполнено\"\n\n"
        "После проверки администратор начислит монеты.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="bank_deposit")]
        ])
    )
    await state.set_state(BankPaymentStates.waiting_for_receipt_photo)
    await callback.answer()

@router.message(BankPaymentStates.waiting_for_receipt_photo, F.photo)
async def process_receipt_photo(message: types.Message, state: FSMContext):
    """Обработка фото чека"""
    data = await state.get_data()
    deposit_id = data.get("deposit_id")
    
    # Получаем ID фото (самое большое качество)
    photo_id = message.photo[-1].file_id
    
    # Сохраняем фото в заявке
    db.update_deposit_receipt(deposit_id, photo_id)
    
    deposit = db.get_bank_deposit(deposit_id)
    user = db.get_user(message.from_user.id)
    
    # Уведомляем всех админов
    for admin_id in ADMIN_IDS:
        try:
            # Клавиатура для админа
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm_bank_{deposit_id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_bank_{deposit_id}")
                ]
            ])
            
            admin_text = (
                f"💰 **Новая заявка на банковское пополнение**\n\n"
                f"👤 Пользователь: {message.from_user.id}\n"
                f"Username: @{message.from_user.username or 'нет'}\n"
                f"Имя: {message.from_user.first_name}\n"
                f"Сумма: {deposit['amount']} руб.\n"
                f"К начислению: {deposit['coins']} монет\n"
                f"Код платежа: `{deposit['code']}`\n"
                f"📅 Создана: {deposit['created_at'][:19]}\n\n"
                f"Чек приложен ниже."
            )
            
            # Отправляем фото с подписью
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=photo_id,
                caption=admin_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления админа {admin_id}: {e}")
    
    await message.answer(
        "✅ **Чек отправлен на проверку!**\n\n"
        f"Администратор проверит платеж и начислит средства в течение 30 минут.\n"
        f"Вы получите уведомление о результате.\n\n"
        f"Номер заявки: #{deposit_id}",
        reply_markup=get_payment_status_keyboard(deposit_id)
    )
    await state.clear()

@router.message(BankPaymentStates.waiting_for_receipt_photo)
async def invalid_receipt(message: types.Message):
    """Обработка не-фото сообщений"""
    await message.answer(
        "❌ Пожалуйста, отправьте фото или скриншот чека.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="bank_deposit")]
        ])
    )

@router.callback_query(F.data.startswith("bank_check_"))
async def check_bank_status(callback: types.CallbackQuery):
    """Проверка статуса заявки"""
    deposit_id = int(callback.data.split("_")[2])
    deposit = db.get_bank_deposit(deposit_id)
    
    if not deposit:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    status_text = {
        "pending": "⏳ Ожидает проверки",
        "completed": "✅ Завершена",
        "rejected": "❌ Отклонена"
    }.get(deposit["status"], "Неизвестно")
    
    text = (
        f"📊 **Статус заявки #{deposit_id}**\n\n"
        f"Статус: {status_text}\n"
        f"Сумма: {deposit['amount']} руб.\n"
        f"К начислению: {deposit['coins']} монет\n"
        f"Код платежа: `{deposit['code']}`\n"
        f"Создана: {deposit['created_at'][:16]}\n"
    )
    
    if deposit["status"] == "completed":
        text += f"Подтверждена: {deposit['completed_at'][:16]}\n"
        text += f"💰 Начислено: +{deposit['coins']} монет"
    elif deposit["status"] == "rejected":
        text += f"Отклонена: {deposit['completed_at'][:16]}\n"
        text += f"❌ Платеж не прошел проверку. Свяжитесь с поддержкой: {SUPPORT_CONTACT}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("bank_deposit")
    )
    await callback.answer()

@router.callback_query(F.data == "bank_history")
async def bank_history(callback: types.CallbackQuery):
    """История банковских пополнений"""
    user_id = callback.from_user.id
    deposits = db.get_user_bank_deposits(user_id)
    
    if not deposits:
        await callback.message.edit_text(
            "📭 У вас пока нет банковских пополнений",
            reply_markup=get_back_keyboard("bank_deposit")
        )
        await callback.answer()
        return
    
    text = "📊 **История банковских пополнений**\n\n"
    
    for d in deposits[:10]:
        status_emoji = {
            "pending": "⏳",
            "completed": "✅",
            "rejected": "❌"
        }.get(d["status"], "❓")
        
        status_text = {
            "pending": "Ожидает",
            "completed": "Зачислено",
            "rejected": "Отклонен"
        }.get(d["status"], d["status"])
        
        date_str = format_time_ago(d['created_at'])
        
        text += f"{status_emoji} **{d['amount']} руб.** = {d['coins']} монет\n"
        text += f"   Код: `{d['code']}`\n"
        text += f"   Статус: {status_text}\n"
        text += f"   Дата: {date_str}\n\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("bank_deposit")
    )
    await callback.answer()