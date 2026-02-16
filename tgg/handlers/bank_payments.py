# handlers/bank_payments.py
import datetime
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import (
    BANK_NAME, BANK_CARD, BANK_ACCOUNT, BANK_BIK,
    RUB_TO_COINS, MIN_DEPOSIT, MIN_WITHDRAW, WITHDRAW_FEE
)
from database import db
from keyboards import (
    get_bank_menu_keyboard, get_deposit_amount_keyboard,
    get_withdraw_amount_keyboard, get_deposit_confirmation_keyboard,
    get_payment_status_keyboard, get_back_keyboard
)
from utils import format_number

router = Router()

class BankPaymentStates(StatesGroup):
    waiting_deposit_custom = State()
    waiting_withdraw_custom = State()
    waiting_card_number = State()
    waiting_card_holder = State()
    waiting_bank_name = State()
    waiting_receipt_photo = State()

@router.callback_query(F.data == "bank_deposit")
async def bank_deposit(callback: types.CallbackQuery):
    """Начало процесса пополнения"""
    await callback.message.edit_text(
        "💰 **Пополнение через банк**\n\n"
        f"Минимальная сумма: {MIN_DEPOSIT} руб.\n"
        f"Курс: 1 рубль = {RUB_TO_COINS} монет\n\n"
        "Выберите сумму пополнения:",
        parse_mode="Markdown",
        reply_markup=get_deposit_amount_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("deposit_amount_"))
async def process_deposit_amount(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбранной суммы пополнения"""
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
        f"**Инструкция:**\n"
        f"1. Переведите **ровно {amount} руб.** на карту:\n"
        f"   `{BANK_CARD}`\n"
        f"2. В комментарии к переводу укажите код: `{deposit['code']}`\n"
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

@router.callback_query(F.data == "deposit_custom")
async def deposit_custom(callback: types.CallbackQuery, state: FSMContext):
    """Ввод своей суммы пополнения"""
    await callback.message.edit_text(
        f"💰 Введите сумму пополнения в рублях (мин. {MIN_DEPOSIT}):",
        reply_markup=get_back_keyboard("bank_deposit")
    )
    await state.set_state(BankPaymentStates.waiting_deposit_custom)
    await callback.answer()

@router.message(BankPaymentStates.waiting_deposit_custom)
async def process_custom_deposit(message: types.Message, state: FSMContext):
    """Обработка своей суммы пополнения"""
    try:
        amount = int(message.text)
        
        if amount < MIN_DEPOSIT:
            await message.answer(
                f"❌ Минимальная сумма: {MIN_DEPOSIT} руб.",
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
            f"**Инструкция:**\n"
            f"1. Переведите **ровно {amount} руб.** на карту:\n"
            f"   `{BANK_CARD}`\n"
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

@router.callback_query(F.data.startswith("confirm_deposit_"))
async def confirm_deposit(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение оплаты и запрос фото чека"""
    deposit_id = int(callback.data.split("_")[2])
    deposit = db.get_bank_deposit(deposit_id)
    
    if not deposit or deposit["status"] != "pending":
        await callback.answer("❌ Заявка не найдена или уже обработана", show_alert=True)
        return
    
    # Проверяем, не истек ли срок
    expires = datetime.datetime.fromisoformat(deposit["expires_at"])
    if datetime.datetime.now() > expires:
        db.reject_deposit(deposit_id, 0)
        await callback.message.edit_text(
            "❌ Срок действия заявки истек. Создайте новую заявку.",
            reply_markup=get_back_keyboard("bank_menu")
        )
        await callback.answer()
        return
    
    await state.update_data(deposit_id=deposit_id)
    
    await callback.message.edit_text(
        "📸 Отправьте фото или скриншот чека об оплате.\n\n"
        "Убедитесь, что на фото виден код платежа и сумма.",
        reply_markup=get_back_keyboard("bank_deposit")
    )
    await state.set_state(BankPaymentStates.waiting_receipt_photo)
    await callback.answer()

@router.message(BankPaymentStates.waiting_receipt_photo, F.photo)
async def process_receipt_photo(message: types.Message, state: FSMContext):
    """Обработка фото чека"""
    from config import ADMIN_IDS
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    data = await state.get_data()
    deposit_id = data.get("deposit_id")
    
    # Получаем ID фото (самое большое качество)
    photo_id = message.photo[-1].file_id
    
    # Сохраняем фото в заявке
    db.update_deposit_receipt(deposit_id, photo_id)
    
    deposit = db.get_bank_deposit(deposit_id)
    
    # Уведомляем всех админов
    for admin_id in ADMIN_IDS:
        try:
            # Клавиатура для админа
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm_deposit_{deposit_id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_deposit_{deposit_id}")
                ]
            ])
            
            # Текст уведомления
            admin_text = (
                f"💰 **Новая заявка на пополнение**\n\n"
                f"ID заявки: {deposit_id}\n"
                f"Пользователь: {message.from_user.id}\n"
                f"Username: @{message.from_user.username or 'нет'}\n"
                f"Сумма: {deposit['amount']} руб.\n"
                f"К начислению: {deposit['coins']} монет\n"
                f"Код платежа: `{deposit['code']}`\n\n"
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
        except:
            pass
    
    await message.answer(
        "✅ **Чек отправлен на проверку!**\n\n"
        "Администратор проверит платеж и начислит средства в течение 30 минут.\n"
        "Вы получите уведомление о результате.",
        reply_markup=get_payment_status_keyboard(deposit_id)
    )
    await state.clear()

@router.message(BankPaymentStates.waiting_receipt_photo)
async def invalid_receipt(message: types.Message):
    """Обработка не-фото сообщений"""
    await message.answer(
        "❌ Пожалуйста, отправьте фото чека.",
        reply_markup=get_back_keyboard("bank_deposit")
    )

@router.callback_query(F.data.startswith("check_deposit_"))
async def check_deposit_status(callback: types.CallbackQuery):
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
        f"Код платежа: `{deposit['code']}`\n"
        f"Создана: {deposit['created_at'][:16]}\n"
    )
    
    if deposit["status"] == "completed":
        text += f"Подтверждена: {deposit['completed_at'][:16]}\n"
        text += f"💰 Начислено: +{deposit['coins']} монет"
    elif deposit["status"] == "rejected":
        text += f"Отклонена: {deposit['completed_at'][:16]}\n"
        text += "❌ Платеж не прошел проверку. Свяжитесь с поддержкой."
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("bank_menu")
    )
    await callback.answer()

@router.callback_query(F.data == "bank_withdraw")
async def bank_withdraw(callback: types.CallbackQuery):
    """Начало процесса вывода"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    
    # Конвертируем монеты в рубли
    max_rub = user['balance'] // RUB_TO_COINS
    
    if max_rub < MIN_WITHDRAW:
        await callback.message.edit_text(
            f"❌ Недостаточно средств для вывода\n\n"
            f"Минимальная сумма вывода: {MIN_WITHDRAW} руб.\n"
            f"Доступно: {max_rub} руб.",
            reply_markup=get_back_keyboard("bank_menu")
        )
        await callback.answer()
        return
    
    text = (
        f"💸 **Вывод средств**\n\n"
        f"💰 Ваш баланс: {format_number(user['balance'])} монет\n"
        f"💵 Доступно для вывода: {max_rub} руб.\n\n"
        f"**Условия вывода:**\n"
        f"• Минимальная сумма: {MIN_WITHDRAW} руб.\n"
        f"• Комиссия: {WITHDRAW_FEE}%\n"
        f"• Срок зачисления: 1-3 рабочих дня\n\n"
        f"Выберите сумму вывода:"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_withdraw_amount_keyboard(max_rub)
    )
    await callback.answer()

# Не забудьте импортировать этот роутер в bot.py