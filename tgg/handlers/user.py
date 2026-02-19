# handlers/user.py
import logging
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from config import (
    REFERRAL_BONUS,
    REFERRAL_BONUS_FRIEND,
    MIN_BET,
    MAX_BET,
    RUB_TO_COINS,
    SUPPORT_CONTACT,
    ADMIN_IDS,
    HELP_TEXT,
    DONATION_INFO_TEXT,
    WITHDRAW_TERMS_TEXT,
)
from database import db
from keyboards import (
    get_main_keyboard,
    get_games_keyboard,
    get_bet_keyboard,
    get_wallet_keyboard,
    get_donation_info_keyboard,
    get_withdraw_menu_keyboard,
    get_support_keyboard,
    get_faq_keyboard,
    get_back_keyboard,
    get_levels_keyboard,
    get_level_info_keyboard,
    get_level_leaderboard_keyboard,
    get_all_levels_keyboard,
)
from utils import (
    roll_dice_with_emoji,
    roll_two_dice,
    format_number,
    generate_referral_link,
    parse_referrer_from_start,
    play_guess_game,
    play_highlow_game,
    play_duel_game,
    play_craps_game,
    get_level_name_with_emoji,
    get_level_progress,
    get_next_level_price,
    format_time_ago,
    calculate_win_chance,
    get_game_difficulty_description,
)

# Настройка логгера
logger = logging.getLogger(__name__)

# Импортируем функции для управления активными играми
from handlers.admin_game_control import register_active_game, unregister_active_game

router = Router()


# Состояния для FSM
class GameStates(StatesGroup):
    waiting_for_guess = State()
    waiting_for_bet = State()
    waiting_for_custom_bet = State()


class WithdrawStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_custom_amount = State()
    waiting_for_card_number = State()
    waiting_for_card_holder = State()
    waiting_for_bank_name = State()


# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================


@router.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandObject):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name

    # Проверяем, есть ли пользователь в БД
    user = db.get_user(user_id)

    if not user:
        # Проверяем реферальный параметр
        referrer_id = None
        if command.args:
            referrer_id = parse_referrer_from_start(command.args)

        # Добавляем пользователя
        db.add_user(user_id, username, first_name, last_name, referrer_id)

        welcome_text = (
            f"🎲 **Добро пожаловать в мир костей!**\n\n"
            f"💰 Вам начислено **{format_number(1000)}** монет\n"
        )

        if referrer_id:
            referrer = db.get_user(referrer_id)
            if referrer:
                welcome_text += f"👥 Вы пришли по приглашению!\n"
                welcome_text += f"🎁 Бонус за регистрацию: +50 монет\n"
    else:
        # Обновляем активность
        db.update_user_activity(user_id)

        # Проверяем, не забанен ли пользователь
        if user.get("is_banned"):
            await message.answer("⛔ Вы заблокированы в боте.")
            return

        welcome_text = f"🎲 **С возвращением!**\n\n"

    # Получаем актуальные данные
    user = db.get_user(user_id)
    balance = user["balance"]

    # Получаем уровень пользователя
    user_level = db.get_user_level(user_id)
    level_display = get_level_name_with_emoji(
        user_level["current_level"], user_level["level_name"]
    )

    # Получаем пользовательскую удачу
    custom_luck = db.get_user_custom_luck(user_id)

    # Проверяем, является ли пользователь админом
    is_admin = user.get("is_admin", False) or (user_id in ADMIN_IDS)

    welcome_text += f"💰 Ваш баланс: **{format_number(balance)}** монет\n"
    welcome_text += (
        f"🎚️ Ваш уровень: {level_display} (x{user_level['luck_multiplier']})\n"
    )

    if custom_luck != 1.0:
        welcome_text += f"⚡ Модификатор удачи: x{custom_luck:.2f}\n"

    total_mult = user_level["luck_multiplier"] * custom_luck
    welcome_text += f"✨ Итоговый множитель: x{total_mult:.2f}\n\n"
    welcome_text += "Выберите действие:"

    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user_id, is_admin),
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда помощи"""
    await message.answer(HELP_TEXT, parse_mode="Markdown")


@router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    """Команда профиля"""
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Ошибка загрузки профиля")
        return

    stats = db.get_user_stats(user_id)
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    level_display = get_level_name_with_emoji(
        user_level["current_level"], user_level["level_name"]
    )

    profile_text = (
        f"👤 **Профиль игрока**\n\n"
        f"ID: `{user_id}`\n"
        f"Имя: {user['first_name'] or 'Не указано'}\n"
        f"Username: @{user['username'] or 'Не указан'}\n\n"
        f"💰 Баланс: **{format_number(user['balance'])}** монет\n"
        f"🎚️ Уровень: {level_display}\n"
        f"✨ Множитель уровня: x{user_level['luck_multiplier']}\n"
        f"⚡ Модификатор удачи: x{custom_luck:.2f}\n"
        f"📊 Итоговый множитель: x{user_level['luck_multiplier'] * custom_luck:.2f}\n"
        f"📅 Всего потрачено на уровни: {format_number(user_level['total_spent'])} монет\n\n"
        f"🎮 Сыграно игр: **{user['total_games']}**\n"
        f"✅ Побед: **{user['total_wins']}**\n"
        f"❌ Поражений: **{user['total_losses']}**\n"
        f"📊 Процент побед: **{stats['win_rate']:.1f}%**\n\n"
        f"👥 Рефералов: **{stats['referrals_count']}**\n"
        f"📅 Регистрация: {user['registration_date'][:10]}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎚️ Уровни", callback_data="level_menu")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
        ]
    )

    await message.answer(profile_text, parse_mode="Markdown", reply_markup=keyboard)


@router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    """Команда баланса"""
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Ошибка загрузки баланса")
        return

    rub_balance = user["balance"] // RUB_TO_COINS
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    await message.answer(
        f"💰 **Ваш баланс**\n\n"
        f"Монет: **{format_number(user['balance'])}**\n"
        f"Рублей: **{rub_balance}**\n\n"
        f"🎚️ Уровень: {user_level['level_name']}\n"
        f"✨ Множитель удачи: x{user_level['luck_multiplier']}\n"
        f"⚡ Модификатор: x{custom_luck:.2f}",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard(),
    )


@router.message(Command("top"))
async def cmd_top(message: types.Message):
    """Команда топа игроков"""
    top = db.get_top_players(10)

    if not top:
        await message.answer("Нет данных о игроках")
        return

    text = "🏆 **Топ игроков по балансу**\n\n"

    for player in top:
        name = (
            player["first_name"] or player["username"] or f"Игрок {player['user_id']}"
        )
        medal = (
            "🥇"
            if player["position"] == 1
            else (
                "🥈"
                if player["position"] == 2
                else "🥉" if player["position"] == 3 else "▫️"
            )
        )

        # Получаем уровень игрока
        player_level = db.get_user_level(player["user_id"])
        level_display = get_level_name_with_emoji(
            player_level["current_level"], player_level["level_name"]
        )

        text += f"{medal} **{player['position']}.** {name}\n"
        text += f"   ├ 💰 {format_number(player['balance'])} монет\n"
        text += f"   ├ 🎚️ {level_display}\n"
        text += (
            f"   └ 🎮 {player['total_games']} игр ({player['total_wins']} побед)\n\n"
        )

    # Добавляем кнопку для топа по уровням
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏆 Топ по уровням", callback_data="level_leaderboard"
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
        ]
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.message(Command("myid"))
async def cmd_myid(message: types.Message):
    """Узнать свой ID"""
    user_id = message.from_user.id
    await message.answer(f"🆔 **Ваш Telegram ID:**\n`{user_id}`", parse_mode="Markdown")


@router.message(Command("support"))
async def cmd_support(message: types.Message):
    """Команда поддержки"""
    await message.answer(
        f"📧 **Поддержка**\n\n"
        f"Свяжитесь с нами: {SUPPORT_CONTACT}\n\n"
        f"Часто задаваемые вопросы:",
        parse_mode="Markdown",
        reply_markup=get_support_keyboard(),
    )


@router.message(Command("level"))
async def cmd_level(message: types.Message):
    """Команда для открытия меню уровней"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    level_display = get_level_name_with_emoji(
        user_level["current_level"], user_level["level_name"]
    )

    text = (
        f"🎚️ **Система уровней**\n\n"
        f"Повышайте свой уровень, чтобы увеличить удачу в играх!\n"
        f"С каждым уровнем растет шанс на дополнительный бонус.\n\n"
        f"**Ваш текущий уровень:**\n"
        f"• {level_display}\n"
        f"• Множитель уровня: x{user_level['luck_multiplier']}\n"
        f"• Модификатор удачи: x{custom_luck:.2f}\n"
        f"• Итоговый множитель: x{user_level['luck_multiplier'] * custom_luck:.2f}\n"
        f"• Всего потрачено: {format_number(user_level['total_spent'])} монет\n\n"
        f"Выберите действие:"
    )

    await message.answer(
        text, parse_mode="Markdown", reply_markup=get_levels_keyboard()
    )


# ============================================
# ОБРАБОТЧИКИ CALLBACK (ОСНОВНОЕ МЕНЮ)
# ============================================


@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    """Показ профиля пользователя"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user:
        await callback.answer("Ошибка загрузки профиля")
        return

    stats = db.get_user_stats(user_id)
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    level_display = get_level_name_with_emoji(
        user_level["current_level"], user_level["level_name"]
    )

    profile_text = (
        f"👤 **Профиль игрока**\n\n"
        f"ID: `{user_id}`\n"
        f"Имя: {user['first_name'] or 'Не указано'}\n"
        f"Username: @{user['username'] or 'Не указан'}\n\n"
        f"💰 Баланс: **{format_number(user['balance'])}** монет\n"
        f"🎚️ Уровень: {level_display}\n"
        f"✨ Множитель уровня: x{user_level['luck_multiplier']}\n"
        f"⚡ Модификатор удачи: x{custom_luck:.2f}\n"
        f"📊 Итоговый множитель: x{user_level['luck_multiplier'] * custom_luck:.2f}\n"
        f"📅 Всего потрачено на уровни: {format_number(user_level['total_spent'])} монет\n\n"
        f"🎮 Сыграно игр: **{user['total_games']}**\n"
        f"✅ Побед: **{user['total_wins']}**\n"
        f"❌ Поражений: **{user['total_losses']}**\n"
        f"📊 Процент побед: **{stats['win_rate']:.1f}%**\n\n"
        f"👥 Рефералов: **{stats['referrals_count']}**\n"
        f"📅 Регистрация: {user['registration_date'][:10]}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎚️ Уровни", callback_data="level_menu")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
        ]
    )

    await callback.message.edit_text(
        profile_text, parse_mode="Markdown", reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "user_stats")
async def show_user_stats(callback: types.CallbackQuery):
    """Показ детальной статистики пользователя"""
    user_id = callback.from_user.id
    stats = db.get_user_stats(user_id)

    if not stats:
        await callback.answer("Ошибка загрузки статистики")
        return

    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    # Создаем прогресс-бар для процента побед
    win_rate = stats["win_rate"]
    progress = "█" * int(win_rate / 10) + "░" * (10 - int(win_rate / 10))

    # Прогресс до следующего уровня
    next_level_price = get_next_level_price(user_level["current_level"])
    level_progress = get_level_progress(
        user_level["current_level"], user_level["total_spent"], next_level_price
    )

    level_display = get_level_name_with_emoji(
        user_level["current_level"], user_level["level_name"]
    )

    stats_text = (
        f"📊 **Детальная статистика**\n\n"
        f"💰 Баланс: **{format_number(stats['balance'])}** монет\n\n"
        f"🎚️ **Прогресс уровня:**\n"
        f"• Текущий: {level_display}\n"
        f"• Множитель уровня: x{user_level['luck_multiplier']}\n"
        f"• Модификатор удачи: x{custom_luck:.2f}\n"
        f"• Итоговый множитель: x{user_level['luck_multiplier'] * custom_luck:.2f}\n"
    )

    if not level_progress["is_max"]:
        progress_bar = "█" * int(level_progress["percentage"] / 10) + "░" * (
            10 - int(level_progress["percentage"] / 10)
        )
        stats_text += (
            f"• Прогресс: {level_progress['percentage']}%\n"
            f"  {progress_bar}\n"
            f"• До следующего: {format_number(level_progress['remaining'])} монет\n\n"
        )
    else:
        stats_text += f"• Достигнут максимальный уровень! 🏆\n\n"

    stats_text += (
        f"🎮 **Игры:**\n"
        f"├ Всего: {stats['total_games']}\n"
        f"├ Побед: {stats['total_wins']}\n"
        f"├ Поражений: {stats['total_losses']}\n"
        f"└ Процент: {win_rate:.1f}%\n"
        f"{progress}\n\n"
        f"💰 **Финансы:**\n"
        f"├ Всего ставок: {format_number(stats['total_bet_amount'])}\n"
        f"├ Всего выиграно: {format_number(stats['total_win_amount'])}\n"
        f"├ Чистая прибыль: {format_number(stats['net_profit'])}\n"
        f"└ Любимая игра: {stats['favorite_game']}\n\n"
        f"👥 Рефералов: {stats['referrals_count']}"
    )

    await callback.message.edit_text(
        stats_text, parse_mode="Markdown", reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "referrals")
async def show_referrals(callback: types.CallbackQuery):
    """Показ реферальной системы"""
    try:
        user_id = callback.from_user.id
        bot_username = (await callback.bot.me()).username

        # Получаем список рефералов
        referrals = db.get_referrals(user_id)

        # Получаем количество рефералов напрямую из БД
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,)
            )
            referrals_count = cursor.fetchone()[0]

        # Генерируем реферальную ссылку
        ref_link = generate_referral_link(bot_username, user_id)

        text = (
            f"👥 **Реферальная система**\n\n"
            f"💰 За каждого приглашенного друга вы получаете **+{REFERRAL_BONUS}** монет\n"
            f"🎁 Друг получает **+{REFERRAL_BONUS_FRIEND}** монет\n\n"
            f"**Ваша статистика:**\n"
            f"├ Приглашено: {referrals_count}\n"
            f"└ Заработано: {referrals_count * REFERRAL_BONUS} монет\n\n"
            f"**Ваша реферальная ссылка:**\n"
            f"`{ref_link}`\n\n"
        )

        if referrals:
            text += "**Ваши рефералы:**\n"
            for i, ref in enumerate(referrals[:5], 1):
                name = (
                    ref.get("first_name")
                    or ref.get("username")
                    or f"ID {ref.get('user_id', 'Неизвестно')}"
                )
                games = ref.get("total_games", 0)
                reg_date = format_time_ago(ref.get("registration_date", ""))
                text += f"{i}. {name} - {games} игр ({reg_date})\n"

            if len(referrals) > 5:
                text += f"...и еще {len(referrals) - 5}"
        else:
            text += "У вас пока нет рефералов. Приглашайте друзей!"

        await callback.message.edit_text(
            text, parse_mode="Markdown", reply_markup=get_back_keyboard()
        )

    except Exception as e:
        print(f"Ошибка в show_referrals: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при загрузке данных. Пожалуйста, попробуйте позже.",
            reply_markup=get_back_keyboard(),
        )
    finally:
        await callback.answer()


@router.callback_query(F.data == "daily_bonus")
async def daily_bonus(callback: types.CallbackQuery):
    """Ежедневный бонус"""
    user_id = callback.from_user.id

    result = db.claim_daily_bonus(user_id)

    if not result:
        await callback.answer("❌ Вы уже получили бонус сегодня!", show_alert=True)
        return

    bonus = result["bonus"]
    streak = result["streak"]

    text = (
        f"🎁 **Ежедневный бонус!**\n\n"
        f"💰 Вы получили **+{bonus}** монет\n"
        f"🔥 Текущий стрик: **{streak}** дней\n\n"
    )

    if streak >= 7:
        text += "🌟 Отличный результат! Так держать!"
    elif streak >= 3:
        text += "✨ Хороший стрик! Продолжайте в том же духе!"

    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    text += f"\n💰 Новый баланс: **{format_number(user['balance'])}** монет"
    text += f"\n🎚️ Ваш уровень: {user_level['level_name']}"
    if custom_luck != 1.0:
        text += f"\n⚡ Модификатор удачи: x{custom_luck:.2f}"

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "top_players")
async def top_players(callback: types.CallbackQuery):
    """Топ игроков по балансу"""
    top = db.get_top_players(10)

    if not top:
        await callback.answer("Нет данных о игроках")
        return

    text = "🏆 **Топ игроков по балансу**\n\n"

    for player in top:
        name = (
            player["first_name"] or player["username"] or f"Игрок {player['user_id']}"
        )
        medal = (
            "🥇"
            if player["position"] == 1
            else (
                "🥈"
                if player["position"] == 2
                else "🥉" if player["position"] == 3 else "▫️"
            )
        )

        # Получаем уровень игрока
        player_level = db.get_user_level(player["user_id"])
        level_display = get_level_name_with_emoji(
            player_level["current_level"], player_level["level_name"]
        )

        text += f"{medal} **{player['position']}.** {name}\n"
        text += f"   ├ 💰 {format_number(player['balance'])} монет\n"
        text += f"   ├ 🎚️ {level_display}\n"
        text += (
            f"   └ 🎮 {player['total_games']} игр ({player['total_wins']} побед)\n\n"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏆 Топ по уровням", callback_data="level_leaderboard"
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


# ============================================
# ОБРАБОТЧИКИ ДЛЯ УРОВНЕЙ
# ============================================


@router.callback_query(F.data == "level_menu")
async def level_menu(callback: types.CallbackQuery):
    """Меню уровней"""
    user_id = callback.from_user.id
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    level_display = get_level_name_with_emoji(
        user_level["current_level"], user_level["level_name"]
    )

    text = (
        f"🎚️ **Система уровней**\n\n"
        f"**Ваш текущий уровень:**\n"
        f"• {level_display}\n"
        f"• Множитель уровня: x{user_level['luck_multiplier']}\n"
        f"• Модификатор удачи: x{custom_luck:.2f}\n"
        f"• Итоговый множитель: x{user_level['luck_multiplier'] * custom_luck:.2f}\n"
        f"• Всего потрачено: {format_number(user_level['total_spent'])} монет\n\n"
        f"Выберите действие:"
    )

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_levels_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_level")
async def my_level(callback: types.CallbackQuery):
    """Информация о текущем уровне"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    level_display = get_level_name_with_emoji(
        user_level["current_level"], user_level["level_name"]
    )

    text = (
        f"📊 **Ваш уровень**\n\n"
        f"**Текущий уровень:** {level_display}\n"
        f"**Множитель уровня:** x{user_level['luck_multiplier']}\n"
        f"**Модификатор удачи:** x{custom_luck:.2f}\n"
        f"**Итоговый множитель:** x{user_level['luck_multiplier'] * custom_luck:.2f}\n"
        f"**Всего потрачено:** {format_number(user_level['total_spent'])} монет\n"
        f"**Баланс:** {format_number(user['balance'])} монет\n\n"
    )

    if user_level["next_level"]:
        next_level = user_level["next_level"]
        progress = get_level_progress(
            user_level["current_level"], user_level["total_spent"], next_level["price"]
        )

        text += (
            f"**Следующий уровень:** {next_level['name']}\n"
            f"**Цена:** {format_number(next_level['price'])} монет\n"
            f"**Новый множитель:** x{next_level['luck_multiplier']}\n"
            f"**Прогресс:** {progress['percentage']}%\n"
        )

        if user["balance"] >= next_level["price"]:
            text += f"\n✅ Вы можете повысить уровень!"
        else:
            need = next_level["price"] - user["balance"]
            text += f"\n❌ Не хватает {format_number(need)} монет"
    else:
        text += f"\n🏆 Вы достигли максимального уровня!"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬆️ Повысить уровень", callback_data="upgrade_level"
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="level_menu")],
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "upgrade_level")
async def upgrade_level(callback: types.CallbackQuery):
    """Повышение уровня"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)

    if not user_level["next_level"]:
        await callback.message.edit_text(
            "🏆 Вы уже достигли максимального уровня!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="my_level")]
                ]
            ),
        )
        await callback.answer()
        return

    next_level = user_level["next_level"]

    if user["balance"] < next_level["price"]:
        need = next_level["price"] - user["balance"]
        await callback.message.edit_text(
            f"❌ Недостаточно монет!\n\n"
            f"**Требуется:** {format_number(next_level['price'])} монет\n"
            f"**Ваш баланс:** {format_number(user['balance'])} монет\n"
            f"**Не хватает:** {format_number(need)} монет",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="my_level")]
                ]
            ),
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

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"confirm_upgrade_{next_level['number']}_{next_level['price']}",
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data="my_level"),
            ]
        ]
    )

    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
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
    if user["balance"] < price:
        await callback.answer("❌ Недостаточно монет!", show_alert=True)
        await my_level(callback)
        return

    # Повышаем уровень
    result = db.upgrade_user_level(user_id)

    if result["success"]:
        custom_luck = db.get_user_custom_luck(user_id)
        new_total_mult = result["new_luck"] * custom_luck

        await callback.message.edit_text(
            f"✅ **Уровень повышен!**\n\n"
            f"**Новый уровень:** {result['level_name']}\n"
            f"**Новый множитель уровня:** x{result['new_luck']}\n"
            f"**Ваш модификатор удачи:** x{custom_luck:.2f}\n"
            f"**Итоговый множитель:** x{new_total_mult:.2f}\n"
            f"**Потрачено:** {format_number(price)} монет\n\n"
            f"Теперь ваша удача увеличилась! ✨",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📊 Мой уровень", callback_data="my_level"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 В меню", callback_data="level_menu"
                        )
                    ],
                ]
            ),
        )
    else:
        await callback.message.edit_text(
            f"❌ Ошибка: {result['message']}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="my_level")]
                ]
            ),
        )

    await callback.answer()


@router.callback_query(F.data == "all_levels")
async def all_levels(callback: types.CallbackQuery):
    """Список всех уровней"""
    user_id = callback.from_user.id
    user_level = db.get_user_level(user_id)
    all_levels = db.get_all_levels()

    await callback.message.edit_text(
        "📋 **Все уровни**\n\n" "Нажмите на уровень для подробной информации:",
        parse_mode="Markdown",
        reply_markup=get_all_levels_keyboard(all_levels, user_level["current_level"]),
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
    custom_luck = db.get_user_custom_luck(user_id)

    is_current = level_num == user_level["current_level"]
    can_upgrade = level_num == user_level["current_level"] + 1

    text = (
        f"📊 **Информация об уровне**\n\n"
        f"**{level['name']}**\n"
        f"**Множитель уровня:** x{level['luck_multiplier']}\n"
        f"**Цена повышения:** {format_number(level['price'])} монет\n\n"
        f"{level['description']}\n\n"
    )

    if is_current:
        text += "✅ **Это ваш текущий уровень**\n"
        text += f"📊 С вашим модификатором x{custom_luck:.2f} итоговый множитель: x{level['luck_multiplier'] * custom_luck:.2f}"
    elif level_num < user_level["current_level"]:
        text += "✅ Вы уже прошли этот уровень"
    else:
        if can_upgrade:
            user = db.get_user(user_id)
            if user["balance"] >= level["price"]:
                text += f"💰 **Доступен для повышения!**\n"
                text += f"✅ У вас достаточно монет"
            else:
                need = level["price"] - user["balance"]
                text += f"💰 **Доступен для повышения**\n"
                text += f"❌ Не хватает {format_number(need)} монет"
        else:
            text += f"🔒 Будет доступен после предыдущих уровней"

    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_level_info_keyboard(level_num, is_current, can_upgrade),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("upgrade_from_info_"))
async def upgrade_from_info(callback: types.CallbackQuery):
    """Повышение уровня из информации об уровне"""
    try:
        level_num = int(callback.data.split("_")[3])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    # Перенаправляем на повышение уровня
    await upgrade_level(callback)


@router.callback_query(F.data == "level_leaderboard")
async def level_leaderboard(callback: types.CallbackQuery):
    """Топ игроков по уровню"""
    leaderboard = db.get_level_leaderboard(10)

    if not leaderboard:
        await callback.message.edit_text(
            "🏆 **Топ игроков по уровню**\n\n" "Пока нет данных",
            reply_markup=get_level_leaderboard_keyboard(),
        )
        await callback.answer()
        return

    text = "🏆 **Топ игроков по уровню**\n\n"

    for player in leaderboard:
        name = (
            player["first_name"] or player["username"] or f"Игрок {player['user_id']}"
        )
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
        total_mult = player["luck_multiplier"] * player["custom_luck"]

        text += f"{medal} **{name}**\n"
        text += f"   ├ Уровень: {level_display}\n"
        text += f"   ├ Множитель уровня: x{player['luck_multiplier']}\n"
        if player["custom_luck"] != 1.0:
            text += f"   ├ Модификатор: x{player['custom_luck']:.2f}\n"
        text += f"   ├ Итоговый: x{total_mult:.2f}\n"
        text += f"   └ Потрачено: {format_number(player['total_spent'])} монет\n\n"

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_level_leaderboard_keyboard()
    )
    await callback.answer()


# ============================================
# ОБРАБОТЧИКИ ДЛЯ КОШЕЛЬКА
# ============================================


@router.callback_query(F.data == "wallet_menu")
async def wallet_menu(callback: types.CallbackQuery):
    """Меню кошелька"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    if not user:
        await callback.answer("Ошибка загрузки данных")
        return

    rub_balance = user["balance"] // RUB_TO_COINS
    total_mult = user_level["luck_multiplier"] * custom_luck

    text = (
        f"💳 **Кошелек**\n\n"
        f"💰 Ваш баланс: **{format_number(user['balance'])}** монет\n"
        f"💵 Эквивалент: **{rub_balance}** руб.\n"
        f"🎚️ Ваш уровень: {user_level['level_name']}\n"
        f"✨ Итоговый множитель: x{total_mult:.2f}\n\n"
        f"**Доступные операции:**\n"
        f"• DonationAlerts - автоматическое пополнение\n"
        f"• Вывод средств на карту\n\n"
        f"Курс обмена: 1 рубль = {RUB_TO_COINS} монет"
    )

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_wallet_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "donation_info")
async def donation_info(callback: types.CallbackQuery):
    """Информация о DonationAlerts"""
    await callback.message.edit_text(
        DONATION_INFO_TEXT,
        parse_mode="Markdown",
        reply_markup=get_donation_info_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "donation_howto")
async def donation_howto(callback: types.CallbackQuery):
    """Как пополнить через DonationAlerts"""
    text = (
        "📋 **Как пополнить через DonationAlerts**\n\n"
        "1. **Узнайте свой ID** командой /myid\n"
        f"   Ваш ID: `{callback.from_user.id}`\n\n"
        "2. **Перейдите на сайт** https://www.donationalerts.com/\n\n"
        "3. **Сделайте донат** на любую сумму\n\n"
        "4. **В комментарии к донату ОБЯЗАТЕЛЬНО укажите** ваш Telegram ID\n\n"
        "5. **Ожидайте** - бот автоматически обнаружит донат\n\n"
        "6. **Администратор проверит** и начислит монеты\n\n"
        f"💰 **Курс:** 1 рубль = {RUB_TO_COINS} монет\n\n"
        "⚠️ **Важно!** Без указания ID в комментарии мы не сможем начислить монеты!"
    )

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard("donation_info")
    )
    await callback.answer()


@router.callback_query(F.data == "donation_history")
async def donation_history(callback: types.CallbackQuery):
    """История донатов пользователя"""
    user_id = callback.from_user.id
    payments = db.get_user_http_payments(user_id)

    if not payments:
        await callback.message.edit_text(
            "📭 У вас пока нет донатов", reply_markup=get_back_keyboard("wallet_menu")
        )
        await callback.answer()
        return

    text = "📊 **История ваших донатов**\n\n"

    for p in payments[:10]:
        status_emoji = {"pending": "⏳", "completed": "✅", "rejected": "❌"}.get(
            p["status"], "❓"
        )

        status_text = {
            "pending": "Ожидает",
            "completed": "Зачислено",
            "rejected": "Отклонен",
        }.get(p["status"], p["status"])

        date_str = format_time_ago(p["created_at"])

        text += f"{status_emoji} **{p['amount']} руб.** = {p['coins']} монет\n"
        text += f"   Статус: {status_text}\n"
        text += f"   Дата: {date_str}\n\n"

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard("wallet_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "withdraw_menu")
async def withdraw_menu(callback: types.CallbackQuery):
    """Меню вывода средств"""
    await callback.message.edit_text(
        WITHDRAW_TERMS_TEXT,
        parse_mode="Markdown",
        reply_markup=get_withdraw_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "withdraw_request")
async def withdraw_request(callback: types.CallbackQuery, state: FSMContext):
    """Запрос на вывод средств"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    max_rub = user["balance"] // RUB_TO_COINS

    if max_rub < 500:
        await callback.message.edit_text(
            f"❌ Недостаточно средств для вывода\n\n"
            f"Минимальная сумма вывода: 500 руб.\n"
            f"Доступно: {max_rub} руб.",
            reply_markup=get_back_keyboard("withdraw_menu"),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"💸 Введите сумму вывода в рублях (от 500 до {max_rub}):",
        reply_markup=get_back_keyboard("withdraw_menu"),
    )
    await state.set_state(WithdrawStates.waiting_for_amount)
    await callback.answer()


@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    """Обработка суммы вывода"""
    try:
        amount = int(message.text)
        user_id = message.from_user.id
        user = db.get_user(user_id)
        max_rub = user["balance"] // RUB_TO_COINS

        if amount < 500:
            await message.answer(
                "❌ Минимальная сумма: 500 руб.",
                reply_markup=get_back_keyboard("withdraw_menu"),
            )
            return

        if amount > max_rub:
            await message.answer(
                f"❌ Максимальная сумма: {max_rub} руб.",
                reply_markup=get_back_keyboard("withdraw_menu"),
            )
            return

        await state.update_data(withdraw_amount=amount)

        await message.answer(
            "💳 Введите номер карты (16 цифр):",
            reply_markup=get_back_keyboard("withdraw_menu"),
        )
        await state.set_state(WithdrawStates.waiting_for_card_number)

    except ValueError:
        await message.answer(
            "❌ Введите число!", reply_markup=get_back_keyboard("withdraw_menu")
        )


@router.message(WithdrawStates.waiting_for_card_number)
async def process_card_number(message: types.Message, state: FSMContext):
    """Обработка номера карты"""
    card_number = message.text.replace(" ", "").replace("-", "")

    if not (card_number.isdigit() and len(card_number) == 16):
        await message.answer(
            "❌ Номер карты должен содержать 16 цифр",
            reply_markup=get_back_keyboard("withdraw_menu"),
        )
        return

    await state.update_data(card_number=card_number)

    await message.answer(
        "👤 Введите имя владельца карты (как на карте):",
        reply_markup=get_back_keyboard("withdraw_menu"),
    )
    await state.set_state(WithdrawStates.waiting_for_card_holder)


@router.message(WithdrawStates.waiting_for_card_holder)
async def process_card_holder(message: types.Message, state: FSMContext):
    """Обработка имени владельца"""
    card_holder = message.text.upper()

    await state.update_data(card_holder=card_holder)

    await message.answer(
        "🏦 Введите название банка:", reply_markup=get_back_keyboard("withdraw_menu")
    )
    await state.set_state(WithdrawStates.waiting_for_bank_name)


@router.message(WithdrawStates.waiting_for_bank_name)
async def process_bank_name(message: types.Message, state: FSMContext):
    """Обработка названия банка"""
    bank_name = message.text

    data = await state.get_data()
    amount = data["withdraw_amount"]
    card_number = data["card_number"]
    card_holder = data["card_holder"]

    user_id = message.from_user.id
    coins_needed = amount * RUB_TO_COINS

    # Создаем заявку на вывод
    request_id = db.create_withdraw_request(
        user_id, amount, card_number, card_holder, bank_name
    )

    if not request_id:
        await message.answer(
            "❌ Ошибка при создании заявки",
            reply_markup=get_back_keyboard("wallet_menu"),
        )
        await state.clear()
        return

    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    await message.answer(
        f"✅ **Заявка на вывод создана!**\n\n"
        f"Номер заявки: #{request_id}\n"
        f"Сумма: {amount} руб.\n"
        f"Списано с баланса: {coins_needed} монет\n"
        f"🎚️ Ваш уровень: {user_level['level_name']}\n"
        f"⚡ Модификатор удачи: x{custom_luck:.2f}\n\n"
        f"Заявка отправлена на обработку. Ожидайте.",
        reply_markup=get_back_keyboard("wallet_menu"),
    )
    await state.clear()


@router.callback_query(F.data == "withdraw_history")
async def withdraw_history(callback: types.CallbackQuery):
    """История выводов"""
    user_id = callback.from_user.id
    withdraws = db.get_user_withdraw_requests(user_id)

    if not withdraws:
        await callback.message.edit_text(
            "📭 У вас пока нет заявок на вывод",
            reply_markup=get_back_keyboard("withdraw_menu"),
        )
        await callback.answer()
        return

    text = "📊 **История выводов**\n\n"

    for w in withdraws[:10]:
        status_emoji = {"pending": "⏳", "completed": "✅", "rejected": "❌"}.get(
            w["status"], "❓"
        )

        date_str = format_time_ago(w["created_at"])

        text += f"{status_emoji} **{w['amount']} руб.**\n"
        text += f"   Карта: {w['card_number'][:4]} **** {w['card_number'][-4:]}\n"
        text += f"   Статус: {w['status']}\n"
        text += f"   Дата: {date_str}\n\n"

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard("withdraw_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "withdraw_terms")
async def withdraw_terms(callback: types.CallbackQuery):
    """Условия вывода"""
    await callback.message.edit_text(
        WITHDRAW_TERMS_TEXT,
        parse_mode="Markdown",
        reply_markup=get_back_keyboard("withdraw_menu"),
    )
    await callback.answer()


# ============================================
# ОБРАБОТЧИКИ ДЛЯ ИГР
# ============================================


@router.callback_query(F.data == "games_menu")
async def games_menu(callback: types.CallbackQuery):
    """Меню игр"""
    user_id = callback.from_user.id
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    total_mult = user_level["luck_multiplier"] * custom_luck

    await callback.message.edit_text(
        f"🎮 **Выберите игру:**\n\n"
        f"🎲 **Угадай число** - x5 (шанс 16.7%)\n"
        f"🎯 **Больше/Меньше 3** - x2 (шанс 16.7%)\n"
        f"🎰 **Дуэль с ботом** - x2 (шанс ~15%)\n"
        f"🎲🎲 **Крэпс** - x1.5 (шанс ~20%)\n\n"
        f"✨ Ваш итоговый множитель удачи: x{total_mult:.2f}",
        parse_mode="Markdown",
        reply_markup=get_games_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("game_"))
async def select_game(callback: types.CallbackQuery, state: FSMContext):
    """Выбор игры"""
    game_type = callback.data.split("_")[1]

    # Сохраняем тип игры
    await state.update_data(game_type=game_type)

    user_id = callback.from_user.id
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    if not user:
        await callback.answer("Ошибка загрузки пользователя")
        return

    if user["balance"] < MIN_BET:
        await callback.message.edit_text(
            f"❌ У вас недостаточно средств для игры!\n"
            f"Минимальная ставка: {MIN_BET} монет\n"
            f"Ваш баланс: {format_number(user['balance'])} монет",
            reply_markup=get_back_keyboard(),
        )
        await callback.answer()
        return

    # Название игры
    game_names = {
        "guess": "Угадай число",
        "highlow": "Больше/Меньше 3",
        "duel": "Дуэль с ботом",
        "craps": "Крэпс",
    }

    game_name = game_names.get(game_type, "Игра")
    game_info = get_game_difficulty_description(game_type)
    win_chance = calculate_win_chance(
        game_type, user_level["luck_multiplier"], custom_luck
    )

    await callback.message.edit_text(
        f"🎮 **{game_name}**\n\n"
        f"💰 Ваш баланс: {format_number(user['balance'])} монет\n"
        f"✨ Множитель удачи: x{user_level['luck_multiplier']}\n"
        f"⚡ Модификатор: x{custom_luck:.2f}\n"
        f"📊 Итоговый множитель: x{user_level['luck_multiplier'] * custom_luck:.2f}\n"
        f"🎲 Шанс на победу: {win_chance:.1f}%\n\n"
        f"{game_info}\n\n"
        f"Выберите сумму ставки:",
        parse_mode="Markdown",
        reply_markup=get_bet_keyboard(MIN_BET, min(MAX_BET, user["balance"])),
    )
    await state.set_state(GameStates.waiting_for_bet)
    await callback.answer()


@router.callback_query(GameStates.waiting_for_bet, F.data.startswith("bet_"))
async def process_bet(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбранной ставки"""
    bet_amount = int(callback.data.split("_")[1])

    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if user["balance"] < bet_amount:
        await callback.message.edit_text(
            "❌ Недостаточно средств!\n"
            f"Ваш баланс: {format_number(user['balance'])} монет\n"
            f"Требуется: {bet_amount} монет",
            reply_markup=get_back_keyboard(),
        )
        await state.clear()
        await callback.answer()
        return

    # Сохраняем ставку
    await state.update_data(bet_amount=bet_amount)

    data = await state.get_data()
    game_type = data.get("game_type")

    if game_type == "guess":
        # Регистрируем активную игру перед ожиданием ввода
        register_active_game(
            user_id=user_id,
            game_type=game_type,
            bet=bet_amount,
            message_id=callback.message.message_id,
            chat_id=callback.message.chat.id,
        )

        await callback.message.edit_text(
            "🎲 Введите число от 1 до 6:", reply_markup=get_back_keyboard("games_menu")
        )
        await state.set_state(GameStates.waiting_for_guess)
    else:
        # Для игр, не требующих ввода, сразу играем
        await play_game(callback.message, state, user_id, game_type, bet_amount)
        await state.clear()

    await callback.answer()


@router.callback_query(GameStates.waiting_for_bet, F.data == "custom_bet")
async def custom_bet(callback: types.CallbackQuery, state: FSMContext):
    """Ввод своей ставки"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    await callback.message.edit_text(
        f"💰 Введите сумму ставки (от {MIN_BET} до {min(MAX_BET, user['balance'])}):\n"
        f"✨ Ваш итоговый множитель: x{user_level['luck_multiplier'] * custom_luck:.2f}",
        reply_markup=get_back_keyboard("games_menu"),
    )
    await state.set_state(GameStates.waiting_for_custom_bet)
    await callback.answer()


@router.message(GameStates.waiting_for_custom_bet)
async def process_custom_bet(message: types.Message, state: FSMContext):
    """Обработка своей ставки"""
    try:
        bet_amount = int(message.text)

        user_id = message.from_user.id
        user = db.get_user(user_id)
        user_level = db.get_user_level(user_id)
        custom_luck = db.get_user_custom_luck(user_id)

        if bet_amount < MIN_BET:
            await message.answer(
                f"❌ Минимальная ставка: {MIN_BET} монет",
                reply_markup=get_back_keyboard("games_menu"),
            )
            return

        if bet_amount > MAX_BET:
            await message.answer(
                f"❌ Максимальная ставка: {MAX_BET} монет",
                reply_markup=get_back_keyboard("games_menu"),
            )
            return

        if bet_amount > user["balance"]:
            await message.answer(
                f"❌ У вас недостаточно средств!\n"
                f"Ваш баланс: {format_number(user['balance'])} монет",
                reply_markup=get_back_keyboard("games_menu"),
            )
            return

        await state.update_data(bet_amount=bet_amount)

        data = await state.get_data()
        game_type = data.get("game_type")

        if game_type == "guess":
            # Регистрируем активную игру
            register_active_game(
                user_id=user_id,
                game_type=game_type,
                bet=bet_amount,
                message_id=message.message_id,
                chat_id=message.chat.id,
            )

            await message.answer(
                "🎲 Введите число от 1 до 6:",
                reply_markup=get_back_keyboard("games_menu"),
            )
            await state.set_state(GameStates.waiting_for_guess)
        else:
            await play_game(message, state, user_id, game_type, bet_amount)
            await state.clear()

    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число!",
            reply_markup=get_back_keyboard("games_menu"),
        )


@router.message(GameStates.waiting_for_guess)
async def process_guess(message: types.Message, state: FSMContext):
    """Обработка угадывания числа"""
    try:
        guess = int(message.text)

        if not (1 <= guess <= 6):
            await message.answer("❌ Введите число от 1 до 6!")
            return

        data = await state.get_data()
        bet_amount = data.get("bet_amount")
        user_id = message.from_user.id

        await play_game(message, state, user_id, "guess", bet_amount, guess)
        await state.clear()

    except ValueError:
        await message.answer("❌ Пожалуйста, введите число!")


async def play_game(
    message_or_callback,
    state,
    user_id: int,
    game_type: str,
    bet_amount: int,
    guess: int = None,
):
    """
    Общая функция для запуска игры с учетом уровня удачи и пользовательской удачи
    """
    # Получаем пользователя
    user = db.get_user(user_id)

    if not user or user["balance"] < bet_amount:
        await message_or_callback.answer("❌ Ошибка: недостаточно средств")
        return

    # Получаем уровень пользователя и множитель удачи
    user_level = db.get_user_level(user_id)
    luck_multiplier = user_level["luck_multiplier"]

    # Получаем пользовательскую удачу (настраивается администратором)
    custom_luck = db.get_user_custom_luck(user_id)

    # СПИСЫВАЕМ СТАВКУ
    db.update_balance(user_id, -bet_amount, "bet", f"Ставка в игре {game_type}")

    # Играем с учетом удачи
    if game_type == "guess" and guess:
        win_amount, result_text = play_guess_game(
            bet_amount, guess, luck_multiplier, custom_luck
        )
    elif game_type == "highlow":
        win_amount, result_text = play_highlow_game(
            bet_amount, luck_multiplier, custom_luck
        )
    elif game_type == "duel":
        win_amount, result_text = play_duel_game(
            bet_amount, luck_multiplier, custom_luck
        )
    elif game_type == "craps":
        win_amount, result_text = play_craps_game(
            bet_amount, luck_multiplier, custom_luck
        )
    else:
        await message_or_callback.answer("❌ Неизвестная игра")
        return

    # НАЧИСЛЯЕМ ВЫИГРЫШ
    if win_amount > 0:
        db.update_balance(user_id, win_amount, "win", f"Выигрыш в игре {game_type}")
        result = "win"
    elif win_amount == bet_amount:
        db.update_balance(
            user_id, bet_amount, "refund", f"Возврат ставки в игре {game_type}"
        )
        result = "draw"
        win_amount = 0
    else:
        result = "loss"
        win_amount = 0

    # Сохраняем результат игры
    db.add_game_result(user_id, game_type, bet_amount, win_amount, result)

    # Удаляем из активных игр
    unregister_active_game(user_id)

    # Получаем обновленный баланс и уровень
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)

    # Добавляем информацию о балансе и уровне
    result_text += f"\n\n💰 Текущий баланс: {format_number(user['balance'])} монет"
    result_text += f"\n🎚️ Ваш уровень: {user_level['level_name']}"

    if custom_luck != 1.0:
        result_text += f"\n⚡ Модификатор удачи: x{custom_luck:.2f}"

    total_mult = luck_multiplier * custom_luck
    result_text += f"\n✨ Итоговый множитель: x{total_mult:.2f}"

    # Проверяем прогресс до следующего уровня
    next_level_price = get_next_level_price(user_level["current_level"])
    if next_level_price:
        progress = (user_level["total_spent"] / next_level_price) * 100
        result_text += f"\n📊 Прогресс до след. уровня: {progress:.1f}%"

    # Проверяем, админ ли пользователь
    is_admin = user.get("is_admin", False) or (user_id in ADMIN_IDS)

    # Отправляем результат
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(
            result_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id, is_admin),
        )
    else:
        await message_or_callback.edit_text(
            result_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id, is_admin),
        )


# ============================================
# ПРОСТЫЕ БРОСКИ КОСТЕЙ
# ============================================


@router.callback_query(F.data == "roll_dice")
async def roll_simple_dice(callback: types.CallbackQuery):
    """Простой бросок кости"""
    value, emoji = roll_dice_with_emoji()

    await callback.message.edit_text(
        f"{emoji} Вам выпало: **{value}**",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "roll_two_dice")
async def roll_two_simple_dice(callback: types.CallbackQuery):
    """Бросок двух костей"""
    d1, d2, total, e1, e2 = roll_two_dice()

    await callback.message.edit_text(
        f"{e1} {e2}\n" f"Вам выпало: **{d1}** и **{d2}**\n" f"Сумма: **{total}**",
        parse_mode="Markdown",
        reply_markup=get_back_keyboard(),
    )
    await callback.answer()


# ============================================
# ПОДДЕРЖКА И FAQ
# ============================================


@router.callback_query(F.data == "support")
async def support_menu(callback: types.CallbackQuery):
    """Меню поддержки"""
    await callback.message.edit_text(
        f"📧 **Поддержка**\n\n"
        f"Свяжитесь с нами: {SUPPORT_CONTACT}\n\n"
        f"Часто задаваемые вопросы:",
        parse_mode="Markdown",
        reply_markup=get_support_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "faq")
async def faq_menu(callback: types.CallbackQuery):
    """Меню FAQ"""
    await callback.message.edit_text(
        "📋 **Часто задаваемые вопросы**\n\n" "Выберите тему:",
        parse_mode="Markdown",
        reply_markup=get_faq_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faq_"))
async def faq_item(callback: types.CallbackQuery):
    """Конкретный вопрос из FAQ"""
    topic = callback.data.split("_")[1]

    faq_texts = {
        "deposit": (
            "💰 **Как получить монеты?**\n\n"
            "1. Сделайте донат через DonationAlerts\n"
            "2. В комментарии укажите ваш Telegram ID\n"
            "3. Администратор проверит и начислит монеты\n\n"
            f"Курс: 1 рубль = {RUB_TO_COINS} монет"
        ),
        "withdraw": (
            "💸 **Как вывести средства?**\n\n"
            "1. Перейдите в Кошелек -> Вывод средств\n"
            "2. Укажите сумму и данные карты\n"
            "3. Администратор обработает заявку\n\n"
            "Срок обработки: 1-3 рабочих дня"
        ),
        "games": (
            "🎲 **Как играть?**\n\n"
            "1. Выберите игру в главном меню\n"
            "2. Укажите сумму ставки\n"
            "3. Сделайте свой ход\n"
            "4. Выигрыш автоматически зачисляется\n\n"
            "Чем выше уровень, тем больше удача!"
        ),
        "referrals": (
            "👥 **Реферальная система**\n\n"
            f"• За приглашение друга: +{REFERRAL_BONUS} монет\n"
            f"• Друг получает: +{REFERRAL_BONUS_FRIEND} монет\n\n"
            "Поделитесь своей реферальной ссылкой из раздела 'Рефералы'"
        ),
        "bonus": (
            "🎁 **Ежедневный бонус**\n\n"
            "Заходите в бот каждый день и получайте бонус!\n"
            "• 1 день: 100 монет\n"
            "• 2 день: 150 монет\n"
            "• 3 день: 200 монет\n"
            "• И так далее (+50 монет каждый день)"
        ),
        "myid": (
            "🆔 **Где найти свой ID?**\n\n"
            f"Ваш Telegram ID: `{callback.from_user.id}`\n\n"
            "Используйте команду /myid в любое время"
        ),
        "levels": (
            "🎚️ **Система уровней**\n\n"
            "Повышайте уровень, чтобы увеличить удачу!\n\n"
            "• 1-3: Бронзовые уровни (x1.0 - x1.1)\n"
            "• 4-6: Серебряные уровни (x1.15 - x1.25)\n"
            "• 7-9: Золотые уровни (x1.3 - x1.4)\n"
            "• 10: Бриллиантовый (x1.5)\n\n"
            "Чем выше уровень, тем больше шанс на бонус!"
        ),
    }

    text = faq_texts.get(topic, "Информация не найдена")

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard("faq")
    )
    await callback.answer()


# ============================================
# НАВИГАЦИЯ
# ============================================


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()

    user_id = callback.from_user.id
    user = db.get_user(user_id)
    user_level = db.get_user_level(user_id)
    custom_luck = db.get_user_custom_luck(user_id)

    if user:
        balance = user["balance"]
        is_admin = user.get("is_admin", False) or (user_id in ADMIN_IDS)
        level_display = get_level_name_with_emoji(
            user_level["current_level"], user_level["level_name"]
        )
        total_mult = user_level["luck_multiplier"] * custom_luck

        await callback.message.edit_text(
            f"💰 Ваш баланс: **{format_number(balance)}** монет\n"
            f"🎚️ Ваш уровень: {level_display}\n"
            f"✨ Итоговый множитель: x{total_mult:.2f}\n\n"
            f"Выберите действие:",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id, is_admin),
        )
    else:
        await callback.message.edit_text(
            "Выберите действие:", reply_markup=get_main_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "cancel_bet")
async def cancel_bet(callback: types.CallbackQuery, state: FSMContext):
    """Отмена ставки"""
    # Удаляем из активных игр при отмене
    user_id = callback.from_user.id
    unregister_active_game(user_id)
    await state.clear()
    await back_to_main(callback, state)


@router.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    """Заглушка для неактивных кнопок"""
    await callback.answer()
