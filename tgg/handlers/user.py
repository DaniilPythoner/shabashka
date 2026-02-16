# handlers/user.py
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import REFERRAL_BONUS, REFERRAL_BONUS_FRIEND, MIN_BET, MAX_BET
from database import db
from keyboards import (
    get_main_keyboard,
    get_games_keyboard,
    get_bet_keyboard,
    get_back_keyboard,
    get_confirmation_keyboard,
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
)

router = Router()


# Состояния для FSM
class GameStates(StatesGroup):
    waiting_for_guess = State()
    waiting_for_bet = State()
    waiting_for_custom_bet = State()


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

    welcome_text += f"💰 Ваш баланс: **{format_number(balance)}** монет\n\n"
    welcome_text += "Выберите действие:"

    # Проверяем, является ли пользователь админом
    is_admin = user.get("is_admin", False)

    await message.answer(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user_id, is_admin),
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда помощи"""
    help_text = """
🎲 **Помощь по боту**

**Команды:**
/start - Запустить бота
/help - Показать эту справку
/profile - Мой профиль
/balance - Мой баланс
/top - Топ игроков

**Игры:**
🎲 Угадай число (x5) - угадайте число от 1 до 6
🎯 Больше/Меньше 3 (x2) - 1-3 проигрыш, 4-5 возврат, 6 выигрыш
🎰 Дуэль с ботом (x2) - у кого больше сумма костей
🎲🎲 Крэпс (x1.5) - классическая игра в кости

**Реферальная система:**
👥 Приглашайте друзей и получайте бонусы
💰 +100 монет за каждого приглашенного
🎁 Друг получает +50 монет

**Ежедневный бонус:**
🎁 Заходите каждый день и получайте бонусы
🔥 С каждым днем стрика бонус увеличивается
"""
    await message.answer(help_text, parse_mode="Markdown")


@router.message(Command("profile"))
async def cmd_profile(message: types.Message):
    """Команда профиля"""
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Ошибка загрузки профиля")
        return

    stats = db.get_user_stats(user_id)

    profile_text = (
        f"👤 **Профиль игрока**\n\n"
        f"ID: `{user_id}`\n"
        f"Имя: {user['first_name'] or 'Не указано'}\n"
        f"Username: @{user['username'] or 'Не указан'}\n\n"
        f"💰 Баланс: **{format_number(user['balance'])}** монет\n"
        f"🎮 Сыграно игр: **{user['total_games']}**\n"
        f"✅ Побед: **{user['total_wins']}**\n"
        f"❌ Поражений: **{user['total_losses']}**\n"
        f"📊 Процент побед: **{stats['win_rate']:.1f}%**\n\n"
        f"👥 Рефералов: **{stats['referrals_count']}**\n"
        f"📅 Регистрация: {user['registration_date'][:10]}"
    )

    await message.answer(
        profile_text, parse_mode="Markdown", reply_markup=get_back_keyboard()
    )


@router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    """Команда баланса"""
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        await message.answer("❌ Ошибка загрузки баланса")
        return

    await message.answer(
        f"💰 Ваш баланс: **{format_number(user['balance'])}** монет",
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

    text = "🏆 **Топ игроков**\n\n"

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

        text += f"{medal} **{player['position']}.** {name}\n"
        text += f"   ├ 💰 {format_number(player['balance'])} монет\n"
        text += (
            f"   └ 🎮 {player['total_games']} игр ({player['total_wins']} побед)\n\n"
        )

    await message.answer(text, parse_mode="Markdown", reply_markup=get_back_keyboard())


@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    """Показ профиля пользователя"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if not user:
        await callback.answer("Ошибка загрузки профиля")
        return

    stats = db.get_user_stats(user_id)

    profile_text = (
        f"👤 **Профиль игрока**\n\n"
        f"ID: `{user_id}`\n"
        f"Имя: {user['first_name'] or 'Не указано'}\n"
        f"Username: @{user['username'] or 'Не указан'}\n\n"
        f"💰 Баланс: **{format_number(user['balance'])}** монет\n"
        f"🎮 Сыграно игр: **{user['total_games']}**\n"
        f"✅ Побед: **{user['total_wins']}**\n"
        f"❌ Поражений: **{user['total_losses']}**\n"
        f"📊 Процент побед: **{stats['win_rate']:.1f}%**\n\n"
        f"👥 Рефералов: **{stats['referrals_count']}**\n"
        f"📅 Регистрация: {user['registration_date'][:10]}"
    )

    await callback.message.edit_text(
        profile_text, parse_mode="Markdown", reply_markup=get_back_keyboard()
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

    # Создаем прогресс-бар для процента побед
    win_rate = stats["win_rate"]
    progress = "█" * int(win_rate / 10) + "░" * (10 - int(win_rate / 10))

    stats_text = (
        f"📊 **Детальная статистика**\n\n"
        f"💰 Баланс: **{format_number(stats['balance'])}** монет\n\n"
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
    user_id = callback.from_user.id
    bot_username = (await callback.bot.me()).username

    referrals = db.get_referrals(user_id)
    stats = db.get_user_stats(user_id)

    # Генерируем реферальную ссылку
    ref_link = generate_referral_link(bot_username, user_id)

    text = (
        f"👥 **Реферальная система**\n\n"
        f"💰 За каждого приглашенного друга вы получаете **+{REFERRAL_BONUS}** монет\n"
        f"🎁 Друг получает **+{REFERRAL_BONUS_FRIEND}** монет\n\n"
        f"**Ваша статистика:**\n"
        f"├ Приглашено: {stats['referrals_count']}\n"
        f"└ Заработано: {stats['referrals_count'] * REFERRAL_BONUS} монет\n\n"
        f"**Ваша реферальная ссылка:**\n"
        f"`{ref_link}`\n\n"
    )

    if referrals:
        text += "**Ваши рефералы:**\n"
        for i, ref in enumerate(referrals[:5], 1):
            name = ref["first_name"] or ref["username"] or f"ID {ref['user_id']}"
            text += f"{i}. {name} - {ref['total_games']} игр\n"

        if len(referrals) > 5:
            text += f"...и еще {len(referrals) - 5}"
    else:
        text += "У вас пока нет рефералов. Приглашайте друзей!"

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard()
    )
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

    text += f"\n💰 Новый баланс: **{format_number(user['balance'])}** монет"

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "top_players")
async def top_players(callback: types.CallbackQuery):
    """Топ игроков"""
    top = db.get_top_players(10)

    if not top:
        await callback.answer("Нет данных о игроках")
        return

    text = "🏆 **Топ игроков**\n\n"

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

        text += f"{medal} **{player['position']}.** {name}\n"
        text += f"   ├ 💰 {format_number(player['balance'])} монет\n"
        text += (
            f"   └ 🎮 {player['total_games']} игр ({player['total_wins']} побед)\n\n"
        )

    await callback.message.edit_text(
        text, parse_mode="Markdown", reply_markup=get_back_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "games_menu")
async def games_menu(callback: types.CallbackQuery):
    """Меню игр"""
    await callback.message.edit_text(
        "🎮 **Выберите игру:**\n\n"
        "🎲 **Угадай число** - x5\n"
        "🎯 **Больше/Меньше 3** - x2\n"
        "🎰 **Дуэль с ботом** - x2\n"
        "🎲🎲 **Крэпс** - x1.5",
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

    await callback.message.edit_text(
        f"🎮 **{game_name}**\n\n"
        f"💰 Ваш баланс: {format_number(user['balance'])} монет\n\n"
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
        await callback.message.edit_text(
            "🎲 Введите число от 1 до 6:", reply_markup=get_back_keyboard("games_menu")
        )
        await state.set_state(GameStates.waiting_for_guess)
    else:
        # Для игр, не требующих ввода
        await play_game(callback.message, state, user_id, game_type, bet_amount)
        await state.clear()

    await callback.answer()


@router.callback_query(GameStates.waiting_for_bet, F.data == "custom_bet")
async def custom_bet(callback: types.CallbackQuery, state: FSMContext):
    """Ввод своей ставки"""
    user_id = callback.from_user.id
    user = db.get_user(user_id)

    await callback.message.edit_text(
        f"💰 Введите сумму ставки (от {MIN_BET} до {min(MAX_BET, user['balance'])}):",
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
    """Общая функция для запуска игры"""
    # Получаем пользователя
    user = db.get_user(user_id)

    if not user or user["balance"] < bet_amount:
        await message_or_callback.answer("❌ Ошибка: недостаточно средств")
        return

    # Списываем ставку
    db.update_balance(user_id, -bet_amount, "bet", f"Ставка в игре {game_type}")

    # Играем
    if game_type == "guess" and guess:
        win_amount, result_text = play_guess_game(bet_amount, guess)
    elif game_type == "highlow":
        win_amount, result_text = play_highlow_game(bet_amount)
    elif game_type == "duel":
        win_amount, result_text = play_duel_game(bet_amount)
    elif game_type == "craps":
        win_amount, result_text = play_craps_game(bet_amount)
    else:
        await message_or_callback.answer("❌ Неизвестная игра")
        return

    # Начисляем выигрыш
    if win_amount > 0:
        net_win = win_amount - bet_amount if win_amount > bet_amount else 0
        if net_win > 0:
            db.update_balance(user_id, net_win, "win", f"Выигрыш в игре {game_type}")
        result = "win"
    elif win_amount == bet_amount:
        # Возврат ставки (ничья)
        db.update_balance(
            user_id, bet_amount, "refund", f"Возврат ставки в игре {game_type}"
        )
        result = "draw"
    else:
        result = "loss"

    # Сохраняем результат игры
    db.add_game_result(user_id, game_type, bet_amount, win_amount, result)

    # Получаем обновленный баланс
    user = db.get_user(user_id)

    # Добавляем информацию о балансе
    result_text += f"\n\n💰 Баланс: {format_number(user['balance'])} монет"

    # Отправляем результат
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(
            result_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id, user.get("is_admin", False)),
        )
    else:
        await message_or_callback.edit_text(
            result_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id, user.get("is_admin", False)),
        )


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


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()

    user_id = callback.from_user.id
    user = db.get_user(user_id)

    if user:
        balance = user["balance"]
        is_admin = user.get("is_admin", False)

        await callback.message.edit_text(
            f"💰 Ваш баланс: **{format_number(balance)}** монет\n\nВыберите действие:",
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
    await state.clear()
    await back_to_main(callback, state)


@router.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    """Заглушка для неактивных кнопок"""
    await callback.answer()
