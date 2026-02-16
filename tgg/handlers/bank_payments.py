# handlers/bank_payments.py
import datetime
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from config import (
    BANK_NAME,
    BANK_CARD,
    BANK_ACCOUNT,
    BANK_BIK,
    RUB_TO_COINS,
    MIN_DEPOSIT,
    MIN_WITHDRAW,
    MAX_WITHDRAW,
    WITHDRAW_FEE,
    ADMIN_IDS,
    CHANNEL_ID,
    CHANNEL_LINK,
    SUPPORT_CONTACT,
)
from database import db
from keyboards import (
    get_bank_menu_keyboard,
    get_deposit_amount_keyboard,
    get_withdraw_amount_keyboard,
    get_deposit_confirmation_keyboard,
    get_payment_status_keyboard,
    get_back_keyboard,
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


async def publish_to_channel(
    bot, message_text: str, photo_id: str = None, keyboard: InlineKeyboardMarkup = None
):
    """Публикация сообщения в канал"""
    try:
        if photo_id:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo_id,
                caption=message_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=message_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        return True
    except TelegramBadRequest as e:
        print(f"Ошибка публикации в канал: {e}")
        return False


@router.callback_query(F.data == "bank_deposit")
async def bank_deposit(callback: types.CallbackQuery):
    """Начало процесса пополнения"""
    await callback.message.edit_text(
        "💰 **Пополнение через банк**\n\n"
        f"Минимальная сумма: {MIN_DEPOSIT} руб.\n"
        f"Курс: 1 рубль = {RUB_TO_COINS} монет\n"
        f"Все операции публикуются в канале: {CHANNEL_LINK}\n\n"
        "Выберите сумму пополнения:",
        parse_mode="Markdown",
        reply_markup=get_deposit_amount_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_amount_"))
async def process_deposit_amount(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбранной суммы пополнения"""
    amount = int(callback.data.split("_")[2])

    user_id = callback.from_user.id
    user = db.get_user(user_id)
    deposit = db.create_bank_deposit(user_id, amount)

    # Сохраняем ID депозита в состояние
    await state.update_data(deposit_id=deposit["id"])

    expires = datetime.datetime.fromisoformat(deposit["expires_at"]).strftime(
        "%d.%m.%Y %H:%M"
    )

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
        f"⚠️ Средства поступят после проверки администратором\n"
        f"📢 Все операции публикуются в канале: {CHANNEL_LINK}"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_deposit_confirmation_keyboard(deposit["id"]),
    )
    await callback.answer()

    # Публикуем в канал о новой заявке
    channel_text = (
        f"🆕 **Новая заявка на пополнение**\n\n"
        f"👤 Пользователь: {user['first_name'] or 'Аноним'} (@{user['username'] or 'нет'})\n"
        f"💰 Сумма: {amount} руб.\n"
        f"🎁 К начислению: {deposit['coins']} монет\n"
        f"🔢 Код: `{deposit['code']}`\n"
        f"⏳ Статус: Ожидает оплаты\n"
        f"📅 Создана: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    await publish_to_channel(callback.bot, channel_text)


@router.callback_query(F.data == "deposit_custom")
async def deposit_custom(callback: types.CallbackQuery, state: FSMContext):
    """Ввод своей суммы пополнения"""
    await callback.message.edit_text(
        f"💰 Введите сумму пополнения в рублях (мин. {MIN_DEPOSIT}):",
        reply_markup=get_back_keyboard("bank_deposit"),
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
                reply_markup=get_back_keyboard("bank_deposit"),
            )
            return

        if amount > 1000000:
            await message.answer(
                "❌ Максимальная сумма: 1 000 000 руб.",
                reply_markup=get_back_keyboard("bank_deposit"),
            )
            return

        user_id = message.from_user.id
        user = db.get_user(user_id)
        deposit = db.create_bank_deposit(user_id, amount)

        await state.update_data(deposit_id=deposit["id"])

        expires = datetime.datetime.fromisoformat(deposit["expires_at"]).strftime(
            "%d.%m.%Y %H:%M"
        )

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
            f"3. После оплаты нажмите кнопку «Я оплатил»\n\n"
            f"📢 Все операции публикуются в канале: {CHANNEL_LINK}"
        )

        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_deposit_confirmation_keyboard(deposit["id"]),
        )
        await state.clear()

        # Публикуем в канал о новой заявке
        channel_text = (
            f"🆕 **Новая заявка на пополнение**\n\n"
            f"👤 Пользователь: {user['first_name'] or 'Аноним'} (@{user['username'] or 'нет'})\n"
            f"💰 Сумма: {amount} руб.\n"
            f"🎁 К начислению: {deposit['coins']} монет\n"
            f"🔢 Код: `{deposit['code']}`\n"
            f"⏳ Статус: Ожидает оплаты\n"
            f"📅 Создана: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        await publish_to_channel(message.bot, channel_text)

    except ValueError:
        await message.answer(
            "❌ Введите число!", reply_markup=get_back_keyboard("bank_deposit")
        )


@router.callback_query(F.data.startswith("confirm_deposit_"))
async def confirm_deposit(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение оплаты и запрос фото чека"""
    deposit_id = int(callback.data.split("_")[2])
    deposit = db.get_bank_deposit(deposit_id)

    if not deposit or deposit["status"] != "pending":
        await callback.answer(
            "❌ Заявка не найдена или уже обработана", show_alert=True
        )
        return

    # Проверяем, не истек ли срок
    expires = datetime.datetime.fromisoformat(deposit["expires_at"])
    if datetime.datetime.now() > expires:
        db.reject_deposit(deposit_id, 0)
        await callback.message.edit_text(
            "❌ Срок действия заявки истек. Создайте новую заявку.",
            reply_markup=get_back_keyboard("bank_menu"),
        )
        await callback.answer()

        # Публикуем в канал об истечении срока
        channel_text = (
            f"⏰ **Срок заявки истек**\n\n"
            f"🆔 Заявка #{deposit_id}\n"
            f"💰 Сумма: {deposit['amount']} руб.\n"
            f"🔢 Код: `{deposit['code']}`\n"
            f"❌ Статус: Отклонена (истек срок)"
        )
        await publish_to_channel(callback.bot, channel_text)
        return

    await state.update_data(deposit_id=deposit_id)

    await callback.message.edit_text(
        "📸 Отправьте фото или скриншот чека об оплате.\n\n"
        "Убедитесь, что на фото виден код платежа и сумма.\n"
        f"Чек будет опубликован в канале: {CHANNEL_LINK}",
        reply_markup=get_back_keyboard("bank_deposit"),
    )
    await state.set_state(BankPaymentStates.waiting_receipt_photo)
    await callback.answer()


@router.message(BankPaymentStates.waiting_receipt_photo, F.photo)
async def process_receipt_photo(message: types.Message, state: FSMContext):
    """Обработка фото чека"""
    from config import ADMIN_IDS

    data = await state.get_data()
    deposit_id = data.get("deposit_id")

    # Получаем ID фото (самое большое качество)
    photo_id = message.photo[-1].file_id

    # Сохраняем фото в заявке
    db.update_deposit_receipt(deposit_id, photo_id)

    deposit = db.get_bank_deposit(deposit_id)
    user = db.get_user(message.from_user.id)

    # Публикуем чек в канал
    channel_text = (
        f"📸 **Новый чек на проверку**\n\n"
        f"🆔 Заявка #{deposit_id}\n"
        f"👤 Пользователь: {user['first_name'] or 'Аноним'} (@{user['username'] or 'нет'})\n"
        f"💰 Сумма: {deposit['amount']} руб.\n"
        f"🎁 К начислению: {deposit['coins']} монет\n"
        f"🔢 Код: `{deposit['code']}`\n"
        f"📅 Отправлен: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"⏳ Ожидает проверки администратором"
    )

    # Клавиатура для админов в канале (опционально)
    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"admin_confirm_deposit_{deposit_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"admin_reject_deposit_{deposit_id}",
                ),
            ]
        ]
    )

    await publish_to_channel(message.bot, channel_text, photo_id, admin_keyboard)

    # Уведомляем админов в личку
    for admin_id in ADMIN_IDS:
        try:
            admin_keyboard_private = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Подтвердить",
                            callback_data=f"admin_confirm_deposit_{deposit_id}",
                        ),
                        InlineKeyboardButton(
                            text="❌ Отклонить",
                            callback_data=f"admin_reject_deposit_{deposit_id}",
                        ),
                    ],
                    [InlineKeyboardButton(text="📢 Открыть канал", url=CHANNEL_LINK)],
                ]
            )

            admin_text = (
                f"💰 **Новая заявка на пополнение**\n\n"
                f"ID заявки: {deposit_id}\n"
                f"Пользователь: {message.from_user.id}\n"
                f"Username: @{message.from_user.username or 'нет'}\n"
                f"Сумма: {deposit['amount']} руб.\n"
                f"К начислению: {deposit['coins']} монет\n"
                f"Код платежа: `{deposit['code']}`\n\n"
                f"Чек также опубликован в канале."
            )

            await message.bot.send_photo(
                chat_id=admin_id,
                photo=photo_id,
                caption=admin_text,
                parse_mode="Markdown",
                reply_markup=admin_keyboard_private,
            )
        except:
            pass

    await message.answer(
        "✅ **Чек отправлен на проверку!**\n\n"
        "Администратор проверит платеж и начислит средства в течение 30 минут.\n"
        f"Статус проверки можно отслеживать в канале: {CHANNEL_LINK}\n"
        "Вы получите уведомление о результате.",
        reply_markup=get_payment_status_keyboard(deposit_id),
    )
    await state.clear()


@router.message(BankPaymentStates.waiting_receipt_photo)
async def invalid_receipt(message: types.Message):
    """Обработка не-фото сообщений"""
    await message.answer(
        "❌ Пожалуйста, отправьте фото чека.",
        reply_markup=get_back_keyboard("bank_deposit"),
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
        "rejected": "❌ Отклонена",
    }.get(deposit["status"], "Неизвестно")

    text = (
        f"📊 **Статус заявки #{deposit_id}**\n\n"
        f"Статус: {status_text}\n"
        f"Сумма: {deposit['amount']} руб.\n"
        f"Код платежа: `{deposit['code']}`\n"
        f"Создана: {deposit['created_at'][:16]}\n"
        f"Канал с операциями: {CHANNEL_LINK}\n"
    )

    if deposit["status"] == "completed":
        text += f"Подтверждена: {deposit['completed_at'][:16]}\n"
        text += f"💰 Начислено: +{deposit['coins']} монет"
    elif deposit["status"] == "rejected":
        text += f"Отклонена: {deposit['completed_at'][:16]}\n"
        text += (
            f"❌ Платеж не прошел проверку. Свяжитесь с поддержкой: {SUPPORT_CONTACT}"
        )

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard("bank_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "bank_withdraw")
async def bank_withdraw(callback: types.CallbackQuery):
    """Начало процесса вывода"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    # Конвертируем монеты в рубли
    max_rub = user["balance"] // RUB_TO_COINS

    if max_rub < MIN_WITHDRAW:
        await callback.message.edit_text(
            f"❌ Недостаточно средств для вывода\n\n"
            f"Минимальная сумма вывода: {MIN_WITHDRAW} руб.\n"
            f"Доступно: {max_rub} руб.\n"
            f"Канал с операциями: {CHANNEL_LINK}",
            reply_markup=get_back_keyboard("bank_menu"),
        )
        await callback.answer()
        return

    text = (
        f"💸 **Вывод средств**\n\n"
        f"💰 Ваш баланс: {format_number(user['balance'])} монет\n"
        f"💵 Доступно для вывода: {max_rub} руб.\n\n"
        f"**Условия вывода:**\n"
        f"• Минимальная сумма: {MIN_WITHDRAW} руб.\n"
        f"• Максимальная сумма: {MAX_WITHDRAW} руб.\n"
        f"• Комиссия: {WITHDRAW_FEE}%\n"
        f"• Срок зачисления: 1-3 рабочих дня\n\n"
        f"Все операции публикуются в канале: {CHANNEL_LINK}\n\n"
        f"Выберите сумму вывода:"
    )

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_withdraw_amount_keyboard(min(max_rub, MAX_WITHDRAW)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("withdraw_amount_"))
async def process_withdraw_amount(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбранной суммы вывода"""
    amount = int(callback.data.split("_")[2])

    await state.update_data(withdraw_amount=amount)

    await callback.message.edit_text(
        "💳 Введите номер карты для вывода средств (16 цифр):",
        reply_markup=get_back_keyboard("bank_withdraw"),
    )
    await state.set_state(BankPaymentStates.waiting_card_number)
    await callback.answer()


@router.callback_query(F.data == "withdraw_custom")
async def withdraw_custom(callback: types.CallbackQuery, state: FSMContext):
    """Ввод своей суммы вывода"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    max_rub = min(user["balance"] // RUB_TO_COINS, MAX_WITHDRAW)

    await callback.message.edit_text(
        f"💸 Введите сумму вывода в рублях (от {MIN_WITHDRAW} до {max_rub}):",
        reply_markup=get_back_keyboard("bank_withdraw"),
    )
    await state.set_state(BankPaymentStates.waiting_withdraw_custom)
    await callback.answer()


@router.message(BankPaymentStates.waiting_withdraw_custom)
async def process_custom_withdraw(message: types.Message, state: FSMContext):
    """Обработка своей суммы вывода"""
    try:
        amount = int(message.text)

        user_id = message.from_user.id
        user = db.get_user(user_id)
        max_rub = user["balance"] // RUB_TO_COINS

        if amount < MIN_WITHDRAW:
            await message.answer(
                f"❌ Минимальная сумма: {MIN_WITHDRAW} руб.",
                reply_markup=get_back_keyboard("bank_withdraw"),
            )
            return

        if amount > MAX_WITHDRAW:
            await message.answer(
                f"❌ Максимальная сумма: {MAX_WITHDRAW} руб.",
                reply_markup=get_back_keyboard("bank_withdraw"),
            )
            return

        if amount > max_rub:
            await message.answer(
                f"❌ Недостаточно средств. Доступно: {max_rub} руб.",
                reply_markup=get_back_keyboard("bank_withdraw"),
            )
            return

        await state.update_data(withdraw_amount=amount)

        await message.answer(
            "💳 Введите номер карты для вывода средств (16 цифр):",
            reply_markup=get_back_keyboard("bank_withdraw"),
        )
        await state.set_state(BankPaymentStates.waiting_card_number)

    except ValueError:
        await message.answer(
            "❌ Введите число!", reply_markup=get_back_keyboard("bank_withdraw")
        )


@router.message(BankPaymentStates.waiting_card_number)
async def process_card_number(message: types.Message, state: FSMContext):
    """Обработка номера карты"""
    card_number = message.text.replace(" ", "").replace("-", "")

    if not (card_number.isdigit() and len(card_number) == 16):
        await message.answer(
            "❌ Номер карты должен содержать 16 цифр. Попробуйте снова:",
            reply_markup=get_back_keyboard("bank_withdraw"),
        )
        return

    await state.update_data(card_number=card_number)

    await message.answer(
        "👤 Введите имя владельца карты (как на карте):",
        reply_markup=get_back_keyboard("bank_withdraw"),
    )
    await state.set_state(BankPaymentStates.waiting_card_holder)


@router.message(BankPaymentStates.waiting_card_holder)
async def process_card_holder(message: types.Message, state: FSMContext):
    """Обработка имени владельца карты"""
    card_holder = message.text.upper()

    await state.update_data(card_holder=card_holder)

    await message.answer(
        "🏦 Введите название банка получателя:",
        reply_markup=get_back_keyboard("bank_withdraw"),
    )
    await state.set_state(BankPaymentStates.waiting_bank_name)


@router.message(BankPaymentStates.waiting_bank_name)
async def process_bank_name(message: types.Message, state: FSMContext):
    """Обработка названия банка"""
    bank_name = message.text

    data = await state.get_data()
    amount = data["withdraw_amount"]
    card_number = data["card_number"]
    card_holder = data["card_holder"]

    user_id = message.from_user.id
    user = db.get_user(user_id)

    # Расчет комиссии
    fee = amount * WITHDRAW_FEE // 100
    receive = amount - fee
    coins_needed = amount * RUB_TO_COINS

    # Создаем заявку на вывод
    request_id = db.create_withdraw_request(
        user_id, amount, card_number, card_holder, bank_name
    )

    if not request_id:
        await message.answer(
            "❌ Ошибка при создании заявки. Недостаточно средств?",
            reply_markup=get_back_keyboard("bank_menu"),
        )
        await state.clear()
        return

    # Публикуем в канал о новой заявке на вывод
    channel_text = (
        f"🆕 **Новая заявка на вывод**\n\n"
        f"🆔 Заявка #{request_id}\n"
        f"👤 Пользователь: {user['first_name'] or 'Аноним'} (@{user['username'] or 'нет'})\n"
        f"💰 Сумма вывода: {amount} руб.\n"
        f"💳 Карта: {card_number[:4]} **** {card_number[-4:]}\n"
        f"👤 Владелец: {card_holder}\n"
        f"🏦 Банк: {bank_name}\n"
        f"📉 Комиссия: {fee} руб.\n"
        f"💵 К получению: {receive} руб.\n"
        f"📅 Создана: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"⏳ Статус: Ожидает обработки"
    )

    await publish_to_channel(message.bot, channel_text)

    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            admin_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Подтвердить",
                            callback_data=f"admin_confirm_withdraw_{request_id}",
                        ),
                        InlineKeyboardButton(
                            text="❌ Отклонить",
                            callback_data=f"admin_reject_withdraw_{request_id}",
                        ),
                    ],
                    [InlineKeyboardButton(text="📢 Открыть канал", url=CHANNEL_LINK)],
                ]
            )

            admin_text = (
                f"💸 **Новая заявка на вывод**\n\n"
                f"ID заявки: {request_id}\n"
                f"Пользователь: {user_id}\n"
                f"Username: @{message.from_user.username or 'нет'}\n"
                f"Сумма: {amount} руб.\n"
                f"К списанию: {coins_needed} монет\n"
                f"Карта: {card_number}\n"
                f"Владелец: {card_holder}\n"
                f"Банк: {bank_name}\n"
                f"Комиссия: {fee} руб.\n"
                f"К выплате: {receive} руб."
            )

            await message.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode="Markdown",
                reply_markup=admin_keyboard,
            )
        except:
            pass

    await message.answer(
        f"✅ **Заявка на вывод создана!**\n\n"
        f"Номер заявки: #{request_id}\n"
        f"Сумма вывода: {amount} руб.\n"
        f"Комиссия: {fee} руб.\n"
        f"К получению: {receive} руб.\n"
        f"Списано с баланса: {coins_needed} монет\n\n"
        f"Заявка отправлена на обработку. Статус можно отслеживать в канале:\n"
        f"{CHANNEL_LINK}\n\n"
        f"Срок обработки: 1-3 рабочих дня.",
        reply_markup=get_back_keyboard("bank_menu"),
    )
    await state.clear()


# Админские обработчики для подтверждения платежей
@router.callback_query(F.data.startswith("admin_confirm_deposit_"))
async def admin_confirm_deposit(callback: types.CallbackQuery):
    """Подтверждение пополнения администратором"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return

    deposit_id = int(callback.data.split("_")[3])

    if db.confirm_deposit(deposit_id, callback.from_user.id):
        deposit = db.get_bank_deposit(deposit_id)
        user = db.get_user(deposit["user_id"])

        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                deposit["user_id"],
                f"✅ **Пополнение подтверждено!**\n\n"
                f"Заявка #{deposit_id}\n"
                f"Сумма: {deposit['amount']} руб.\n"
                f"💰 Начислено: +{deposit['coins']} монет\n"
                f"Новый баланс: {format_number(user['balance'])} монет",
                parse_mode="Markdown",
            )
        except:
            pass

        # Публикуем в канал
        channel_text = (
            f"✅ **Пополнение подтверждено**\n\n"
            f"🆔 Заявка #{deposit_id}\n"
            f"👤 Пользователь: {user['first_name'] or 'Аноним'} (@{user['username'] or 'нет'})\n"
            f"💰 Сумма: {deposit['amount']} руб.\n"
            f"🎁 Начислено: +{deposit['coins']} монет\n"
            f"👨‍💼 Администратор: @{callback.from_user.username or 'админ'}\n"
            f"📅 Подтверждена: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        await publish_to_channel(callback.bot, channel_text)

        await callback.answer("✅ Пополнение подтверждено", show_alert=True)
        await callback.message.delete()
    else:
        await callback.answer("❌ Ошибка при подтверждении", show_alert=True)


@router.callback_query(F.data.startswith("admin_reject_deposit_"))
async def admin_reject_deposit(callback: types.CallbackQuery):
    """Отклонение пополнения администратором"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return

    deposit_id = int(callback.data.split("_")[3])

    if db.reject_deposit(deposit_id, callback.from_user.id):
        deposit = db.get_bank_deposit(deposit_id)
        user = db.get_user(deposit["user_id"])

        # Уведомляем пользователя
        try:
            await callback.bot.send_message(
                deposit["user_id"],
                f"❌ **Пополнение отклонено**\n\n"
                f"Заявка #{deposit_id}\n"
                f"Сумма: {deposit['amount']} руб.\n\n"
                f"Причина: платеж не прошел проверку.\n"
                f"Свяжитесь с поддержкой: {SUPPORT_CONTACT}",
                parse_mode="Markdown",
            )
        except:
            pass

        # Публикуем в канал
        channel_text = (
            f"❌ **Пополнение отклонено**\n\n"
            f"🆔 Заявка #{deposit_id}\n"
            f"👤 Пользователь: {user['first_name'] or 'Аноним'} (@{user['username'] or 'нет'})\n"
            f"💰 Сумма: {deposit['amount']} руб.\n"
            f"👨‍💼 Администратор: @{callback.from_user.username or 'админ'}\n"
            f"📅 Отклонена: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        await publish_to_channel(callback.bot, channel_text)

        await callback.answer("✅ Пополнение отклонено", show_alert=True)
        await callback.message.delete()
    else:
        await callback.answer("❌ Ошибка при отклонении", show_alert=True)


@router.callback_query(F.data.startswith("admin_confirm_withdraw_"))
async def admin_confirm_withdraw(callback: types.CallbackQuery):
    """Подтверждение вывода администратором"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return

    request_id = int(callback.data.split("_")[3])

    if db.confirm_withdraw(request_id, callback.from_user.id):
        # Получаем информацию о заявке
        requests = db.get_withdraw_requests("pending")
        request = next((r for r in requests if r["id"] == request_id), None)

        if request:
            user = db.get_user(request["user_id"])

            # Уведомляем пользователя
            try:
                fee = request["amount"] * WITHDRAW_FEE // 100
                receive = request["amount"] - fee

                await callback.bot.send_message(
                    request["user_id"],
                    f"✅ **Вывод подтвержден!**\n\n"
                    f"Заявка #{request_id}\n"
                    f"Сумма вывода: {request['amount']} руб.\n"
                    f"Комиссия: {fee} руб.\n"
                    f"К получению: {receive} руб.\n"
                    f"Карта: {request['card_number'][:4]} **** {request['card_number'][-4:]}\n\n"
                    f"Средства будут отправлены в течение 1-3 рабочих дней.",
                    parse_mode="Markdown",
                )
            except:
                pass

            # Публикуем в канал
            channel_text = (
                f"✅ **Вывод подтвержден**\n\n"
                f"🆔 Заявка #{request_id}\n"
                f"👤 Пользователь: {user['first_name'] or 'Аноним'} (@{user['username'] or 'нет'})\n"
                f"💰 Сумма: {request['amount']} руб.\n"
                f"💳 Карта: {request['card_number'][:4]} **** {request['card_number'][-4:]}\n"
                f"👨‍💼 Администратор: @{callback.from_user.username or 'админ'}\n"
                f"📅 Подтверждена: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )

            await publish_to_channel(callback.bot, channel_text)

        await callback.answer("✅ Вывод подтвержден", show_alert=True)
        await callback.message.delete()
    else:
        await callback.answer("❌ Ошибка при подтверждении", show_alert=True)


@router.callback_query(F.data.startswith("admin_reject_withdraw_"))
async def admin_reject_withdraw(callback: types.CallbackQuery):
    """Отклонение вывода администратором"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ У вас нет прав администратора", show_alert=True)
        return

    request_id = int(callback.data.split("_")[3])

    if db.reject_withdraw(request_id, callback.from_user.id):
        # Получаем информацию о заявке
        requests = db.get_withdraw_requests("pending")
        request = next((r for r in requests if r["id"] == request_id), None)

        if request:
            user = db.get_user(request["user_id"])

            # Уведомляем пользователя
            try:
                await callback.bot.send_message(
                    request["user_id"],
                    f"❌ **Вывод отклонен**\n\n"
                    f"Заявка #{request_id}\n"
                    f"Сумма: {request['amount']} руб.\n\n"
                    f"Средства возвращены на ваш баланс.\n"
                    f"Свяжитесь с поддержкой: {SUPPORT_CONTACT}",
                    parse_mode="Markdown",
                )
            except:
                pass

            # Публикуем в канал
            channel_text = (
                f"❌ **Вывод отклонен**\n\n"
                f"🆔 Заявка #{request_id}\n"
                f"👤 Пользователь: {user['first_name'] or 'Аноним'} (@{user['username'] or 'нет'})\n"
                f"💰 Сумма: {request['amount']} руб.\n"
                f"💳 Карта: {request['card_number'][:4]} **** {request['card_number'][-4:]}\n"
                f"👨‍💼 Администратор: @{callback.from_user.username or 'админ'}\n"
                f"📅 Отклонена: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )

            await publish_to_channel(callback.bot, channel_text)

        await callback.answer("✅ Вывод отклонен, средства возвращены", show_alert=True)
        await callback.message.delete()
    else:
        await callback.answer("❌ Ошибка при отклонении", show_alert=True)
