# handlers/donation_payments.py
import time
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MIN_DEPOSIT, RUB_TO_COINS, ADMIN_IDS, SUPPORT_CONTACT, CHANNEL_LINK
from database import db
from donationalerts import donationalerts
from utils import format_number
import datetime

router = Router()


class DonationManualStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_custom_amount = State()
    waiting_for_screenshot = State()


def get_donation_amount_keyboard():
    """Клавиатура выбора суммы пополнения"""
    builder = InlineKeyboardBuilder()

    amounts = [100, 300, 500, 1000, 2000, 5000]

    for amount in amounts:
        coins = amount * RUB_TO_COINS
        builder.row(
            InlineKeyboardButton(
                text=f"💰 {amount} руб. = {coins} монет",
                callback_data=f"da_manual_amount_{amount}",
            ),
            width=1,
        )

    builder.row(
        InlineKeyboardButton(text="✏️ Другая сумма", callback_data="da_manual_custom"),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="📋 Мои платежи", callback_data="da_manual_history"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="wallet_menu"),
        width=2,
    )

    return builder.as_markup()


def get_donation_payment_keyboard(payment_id: str, payment_url: str):
    """Клавиатура для оплаты"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url), width=1
    )
    builder.row(
        InlineKeyboardButton(
            text="📸 Я оплатил (прислать чек)",
            callback_data=f"da_manual_send_screenshot_{payment_id}",
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_menu"), width=1
    )

    return builder.as_markup()


def get_payment_status_keyboard(payment_id: str):
    """Клавиатура для проверки статуса"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔄 Проверить статус", callback_data=f"da_manual_check_{payment_id}"
        ),
        width=1,
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="da_manual_history"),
        width=1,
    )

    return builder.as_markup()


@router.callback_query(F.data == "donation_deposit")
async def donation_deposit(callback: types.CallbackQuery):
    """Начало процесса пополнения"""
    await callback.message.edit_text(
        "💰 **Пополнение через DonationAlerts**\n\n"
        f"Минимальная сумма: {MIN_DEPOSIT} руб.\n"
        f"Курс: 1 рубль = {RUB_TO_COINS} монет\n"
        f"Способ: ручная проверка администратором\n\n"
        "**Как это работает:**\n"
        "1. Вы выбираете сумму\n"
        "2. Переходите по ссылке для оплаты\n"
        "3. После оплаты присылаете скриншот чека\n"
        "4. Администратор проверяет и начисляет монеты\n\n"
        "Выберите сумму пополнения:",
        parse_mode="Markdown",
        reply_markup=get_donation_amount_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("da_manual_amount_"))
async def process_da_amount(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбранной суммы"""
    amount = int(callback.data.split("_")[3])
    await create_donation_payment(callback.message, callback.from_user.id, amount)
    await callback.answer()


@router.callback_query(F.data == "da_manual_custom")
async def da_custom_amount(callback: types.CallbackQuery, state: FSMContext):
    """Ввод своей суммы"""
    await callback.message.edit_text(
        f"💰 Введите сумму пополнения в рублях (мин. {MIN_DEPOSIT}):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="donation_deposit"
                    )
                ]
            ]
        ),
    )
    await state.set_state(DonationManualStates.waiting_for_custom_amount)
    await callback.answer()


@router.message(DonationManualStates.waiting_for_custom_amount)
async def process_custom_da_amount(message: types.Message, state: FSMContext):
    """Обработка своей суммы"""
    try:
        amount = int(message.text)

        if amount < MIN_DEPOSIT:
            await message.answer(
                f"❌ Минимальная сумма: {MIN_DEPOSIT} руб.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🔙 Назад", callback_data="donation_deposit"
                            )
                        ]
                    ]
                ),
            )
            return

        if amount > 100000:
            await message.answer(
                "❌ Максимальная сумма: 100 000 руб.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🔙 Назад", callback_data="donation_deposit"
                            )
                        ]
                    ]
                ),
            )
            return

        await create_donation_payment(message, message.from_user.id, amount)
        await state.clear()

    except ValueError:
        await message.answer(
            "❌ Введите число!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="donation_deposit"
                        )
                    ]
                ]
            ),
        )


async def create_donation_payment(message_or_callback, user_id: int, amount: int):
    """Создание платежа через DonationAlerts"""
    coins = amount * RUB_TO_COINS

    # Создаем платеж в DonationAlerts
    payment_data = await donationalerts.create_payment(
        amount=amount, description=f"Пополнение баланса на {coins} монет"
    )

    if not payment_data:
        error_text = (
            "❌ **Ошибка создания платежа**\n\n"
            "Не удалось подключиться к DonationAlerts. Попробуйте позже."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="wallet_menu")]
            ]
        )

        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(
                error_text, parse_mode="Markdown", reply_markup=keyboard
            )
        else:
            await message_or_callback.edit_text(
                error_text, parse_mode="Markdown", reply_markup=keyboard
            )
        return

    # Сохраняем платеж в базу данных
    db.create_da_manual_payment(
        user_id=user_id,
        amount=amount,
        coins=coins,
        payment_id=payment_data["payment_id"],
        order_id=payment_data["order_id"],
        payment_url=payment_data["payment_url"],
    )

    text = (
        f"💰 **Платеж создан!**\n\n"
        f"Сумма: **{amount} руб.**\n"
        f"К начислению: **{coins}** монет\n"
        f"ID платежа: `{payment_data['payment_id']}`\n\n"
        f"**Инструкция:**\n"
        f"1. Нажмите кнопку «Перейти к оплате»\n"
        f"2. Оплатите на сайте DonationAlerts\n"
        f"3. После оплаты нажмите «Я оплатил» и пришлите скриншот\n"
        f"4. Ожидайте проверки администратором\n\n"
        f"⏳ Средства поступят после проверки (обычно до 30 минут)"
    )

    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_donation_payment_keyboard(
                payment_data["payment_id"], payment_data["payment_url"]
            ),
        )
    else:
        await message_or_callback.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_donation_payment_keyboard(
                payment_data["payment_id"], payment_data["payment_url"]
            ),
        )


@router.callback_query(F.data.startswith("da_manual_send_screenshot_"))
async def da_send_screenshot(callback: types.CallbackQuery, state: FSMContext):
    """Запрос скриншота после оплаты"""
    payment_id = callback.data.split("_")[4]

    payment = db.get_da_manual_payment(payment_id)

    if not payment:
        await callback.answer("❌ Платеж не найден", show_alert=True)
        return

    if payment["status"] != "pending":
        await callback.answer("❌ Этот платеж уже обработан", show_alert=True)
        return

    await state.update_data(payment_id=payment_id)

    await callback.message.edit_text(
        "📸 **Отправьте скриншот подтверждения оплаты**\n\n"
        "Пришлите скриншот или фото чека об оплате.\n"
        "На скриншоте должны быть видны:\n"
        "• Сумма платежа\n"
        "• Дата и время\n"
        '• Статус "Оплачено"\n\n'
        "После проверки администратор начислит монеты.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet_menu")]
            ]
        ),
    )
    await state.set_state(DonationManualStates.waiting_for_screenshot)
    await callback.answer()


@router.message(DonationManualStates.waiting_for_screenshot, F.photo)
async def process_screenshot(message: types.Message, state: FSMContext):
    """Обработка скриншота"""
    data = await state.get_data()
    payment_id = data.get("payment_id")

    # Получаем ID фото (самое большое качество)
    photo_id = message.photo[-1].file_id

    # Сохраняем скриншот в заявке
    db.update_da_payment_screenshot(payment_id, photo_id)

    payment = db.get_da_manual_payment(payment_id)
    user = db.get_user(message.from_user.id)

    # Уведомляем всех админов
    for admin_id in ADMIN_IDS:
        try:
            # Клавиатура для админа
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

            admin_text = (
                f"💰 **Новая заявка на пополнение (DonationAlerts)**\n\n"
                f"👤 Пользователь: {message.from_user.id}\n"
                f"Username: @{message.from_user.username or 'нет'}\n"
                f"Имя: {message.from_user.first_name}\n"
                f"Сумма: {payment['amount']} руб.\n"
                f"К начислению: {payment['coins']} монет\n"
                f"ID платежа: `{payment_id}`\n"
                f"📅 Создана: {payment['created_at'][:19]}\n\n"
                f"Чек приложен ниже."
            )

            # Отправляем фото с подписью
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=photo_id,
                caption=admin_text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception as e:
            print(f"Ошибка уведомления админа {admin_id}: {e}")

    await message.answer(
        "✅ **Скриншот отправлен на проверку!**\n\n"
        f"Администратор проверит платеж и начислит средства в течение 30 минут.\n"
        f"Вы получите уведомление о результате.\n\n"
        f"ID платежа: `{payment_id}`",
        parse_mode="Markdown",
        reply_markup=get_payment_status_keyboard(payment_id),
    )
    await state.clear()


@router.message(DonationManualStates.waiting_for_screenshot)
async def invalid_screenshot(message: types.Message):
    """Обработка не-фото сообщений"""
    await message.answer(
        "❌ Пожалуйста, отправьте фото или скриншот чека.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="wallet_menu")]
            ]
        ),
    )


@router.callback_query(F.data.startswith("da_manual_check_"))
async def check_payment_status(callback: types.CallbackQuery):
    """Проверка статуса платежа"""
    payment_id = callback.data.split("_")[3]

    payment = db.get_da_manual_payment(payment_id)

    if not payment:
        await callback.answer("❌ Платеж не найден", show_alert=True)
        return

    status_text = {
        "pending": "⏳ Ожидает проверки",
        "completed": "✅ Завершен",
        "rejected": "❌ Отклонен",
    }.get(payment["status"], "Неизвестно")

    text = (
        f"📊 **Статус платежа**\n\n"
        f"ID: `{payment_id}`\n"
        f"Сумма: {payment['amount']} руб.\n"
        f"К начислению: {payment['coins']} монет\n"
        f"Статус: {status_text}\n"
        f"Создан: {payment['created_at'][:19]}\n"
    )

    if payment["status"] == "completed":
        text += f"Подтвержден: {payment['completed_at'][:19]}\n"
        text += f"💰 Начислено: +{payment['coins']} монет"
    elif payment["status"] == "rejected":
        text += f"Отклонен: {payment['completed_at'][:19]}\n"
        text += f"❌ Причина: платеж не прошел проверку. Свяжитесь с поддержкой: {SUPPORT_CONTACT}"

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="da_manual_history"
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "da_manual_history")
async def da_payment_history(callback: types.CallbackQuery):
    """История платежей"""
    user_id = callback.from_user.id
    payments = db.get_user_da_manual_payments(user_id)

    if not payments:
        await callback.message.edit_text(
            "📭 У вас пока нет платежей через DonationAlerts",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💰 Пополнить", callback_data="donation_deposit"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад", callback_data="wallet_menu"
                        )
                    ],
                ]
            ),
        )
        await callback.answer()
        return

    text = "📊 **История платежей DonationAlerts**\n\n"

    for p in payments[:5]:
        status_emoji = {"pending": "⏳", "completed": "✅", "rejected": "❌"}.get(
            p["status"], "❓"
        )

        status_text = {
            "pending": "Ожидает",
            "completed": "Завершен",
            "rejected": "Отклонен",
        }.get(p["status"], p["status"])

        text += f"{status_emoji} **{p['amount']} руб.** = {p['coins']} монет\n"
        text += f"   ID: `{p['payment_id'][:8]}...`\n"
        text += f"   Статус: {status_text}\n"
        text += f"   Дата: {p['created_at'][:16]}\n\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Новый платеж", callback_data="donation_deposit"
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="wallet_menu")],
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()
