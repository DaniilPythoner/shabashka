# bot.py
import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.utils.token import TokenValidationError

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Импорт конфигурации (без dotenv)
try:
    from config import (
        BOT_TOKEN,
        ADMIN_IDS,
        DONATION_ALERTS_WIDGET_TOKEN,
        RUB_TO_COINS,
        MIN_DEPOSIT,
        SUPPORT_CONTACT,
        DONATION_POLL_INTERVAL,
        HTTP_TIMEOUT,
        HELP_TEXT,
        DONATION_INFO_TEXT,
        WITHDRAW_TERMS_TEXT,
    )
    from config import (
        START_BALANCE,
        MIN_BET,
        MAX_BET,
        REFERRAL_BONUS,
        REFERRAL_BONUS_FRIEND,
    )
except ImportError as e:
    logger.error(f"❌ Ошибка импорта config.py: {e}")
    print("\n❌ ОШИБКА: Не удалось импортировать config.py")
    print(
        "Убедитесь, что файл config.py существует и содержит все необходимые настройки"
    )
    sys.exit(1)

# Проверяем наличие токена
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не указан в config.py!")
    print("\n❌ ОШИБКА: BOT_TOKEN не указан!")
    print("Укажите токен в файле config.py")
    print("Пример: BOT_TOKEN = '1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890'")
    sys.exit(1)

# Импорт базы данных
try:
    from database import db

    logger.info("✅ База данных подключена")
    # Инициализируем уровни при запуске
    db.init_levels()
    logger.info("✅ Система уровней инициализирована")
except Exception as e:
    logger.error(f"❌ Ошибка подключения к базе данных: {e}")
    print(f"\n❌ ОШИБКА: Не удалось подключиться к базе данных: {e}")
    sys.exit(1)

# Импорт обработчиков
try:
    from handlers import user, admin, http_bind, admin_game_control, levels

    logger.info("✅ Обработчики импортированы")
    logger.info(f"   - user.py: загружен (пользовательский интерфейс)")
    logger.info(f"   - admin.py: загружен (админ-панель)")
    logger.info(f"   - http_bind.py: загружен (DonationAlerts)")
    logger.info(f"   - admin_game_control.py: загружен (управление играми)")
    logger.info(f"   - levels.py: загружен (система уровней)")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта обработчиков: {e}")
    print(f"\n❌ ОШИБКА: Не удалось импортировать обработчики: {e}")
    print("Убедитесь, что все файлы в папке handlers существуют:")
    print("  - handlers/__init__.py")
    print("  - handlers/user.py")
    print("  - handlers/admin.py")
    print("  - handlers/http_bind.py")
    print("  - handlers/admin_game_control.py")
    print("  - handlers/levels.py")
    sys.exit(1)

# Импорт DonationAlerts HTTP Poller
try:
    from donation_polling import DonationPoller

    donation_poller = None
    logger.info("✅ DonationAlerts HTTP Poller импортирован")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта donation_polling.py: {e}")
    donation_poller = None

# Импорт DonationAlerts HTTP клиента
try:
    from donationalerts_http import DonationAlertsHTTP

    logger.info("✅ DonationAlerts HTTP клиент импортирован")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта donationalerts_http.py: {e}")


async def set_bot_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="help", description="📖 Помощь"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="balance", description="💰 Мой баланс"),
        BotCommand(command="level", description="🎚️ Система уровней"),
        BotCommand(command="top", description="🏆 Топ игроков"),
        BotCommand(command="myid", description="🆔 Мой ID"),
        BotCommand(command="admin", description="⚙️ Админ-панель"),
        BotCommand(command="support", description="📧 Поддержка"),
        BotCommand(command="active_games", description="🎮 Активные игры (админ)"),
        BotCommand(command="stats", description="📊 Статистика (админ)"),
        BotCommand(command="levels_top", description="🏆 Топ по уровням"),
    ]

    try:
        await bot.set_my_commands(commands)
        logger.info("✅ Команды бота установлены")
    except Exception as e:
        logger.error(f"❌ Ошибка при установке команд: {e}")


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("🚀 Бот запускается...")

    # Запускаем опрос донатов
    global donation_poller
    if DONATION_ALERTS_WIDGET_TOKEN:
        try:
            from donation_polling import DonationPoller

            donation_poller = DonationPoller(bot)
            if donation_poller.start():
                logger.info(
                    f"✅ Опрос донатов DonationAlerts запущен (интервал: {DONATION_POLL_INTERVAL} сек)"
                )
            else:
                logger.warning("⚠️ Опрос донатов не запущен")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска опроса донатов: {e}")
    else:
        logger.warning(
            "⚠️ DONATION_ALERTS_WIDGET_TOKEN не указан, опрос донатов отключен"
        )

    # Получаем количество активных игр
    active_games_count = 0
    try:
        from handlers.admin_game_control import active_games

        active_games_count = len(active_games)
    except:
        pass

    # Получаем общую статистику
    total_users = db.get_total_users_count()
    total_games = db.get_total_games_count()

    # Отправляем уведомление админам
    poller_status = (
        "✅ Активен" if donation_poller and donation_poller.running else "❌ Не активен"
    )
    token_status = "✅ Указан" if DONATION_ALERTS_WIDGET_TOKEN else "❌ Не указан"

    from datetime import datetime

    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✅ **Бот успешно запущен!**\n\n"
                f"📊 **Общая статистика:**\n"
                f"• Пользователей: {total_users}\n"
                f"• Сыграно игр: {total_games}\n"
                f"• Активных игр: {active_games_count}\n\n"
                f"📊 **Статус систем:**\n"
                f"• DonationAlerts Token: {token_status}\n"
                f"• HTTP Polling: {poller_status}\n"
                f"• Интервал проверки: {DONATION_POLL_INTERVAL} сек\n"
                f"• Курс обмена: 1 рубль = {RUB_TO_COINS} монет\n\n"
                f"🎚️ **Система уровней:**\n"
                f"• Всего уровней: 10\n"
                f"• Макс. множитель: x1.5\n\n"
                f"🆔 Ваш ID: `{admin_id}`\n"
                f"📅 Время запуска: {current_time}\n\n"
                f"🎮 **Управление играми:** /active_games\n"
                f"🎚️ **Управление уровнями:** /level",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")

    logger.info("✅ Бот запущен")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("🛑 Бот останавливается...")

    # Останавливаем опрос донатов
    global donation_poller
    if donation_poller:
        donation_poller.stop()
        logger.info("✅ Опрос донатов остановлен")

    # Получаем количество активных игр перед остановкой
    active_games_count = 0
    try:
        from handlers.admin_game_control import active_games

        active_games_count = len(active_games)
        if active_games_count > 0:
            logger.warning(
                f"⚠️ Осталось {active_games_count} активных игр при остановке бота"
            )
    except:
        pass

    # Отправляем уведомление админам
    from datetime import datetime

    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🛑 **Бот остановлен!**\n\n"
                f"📅 Время остановки: {current_time}\n"
                f"🎮 Активных игр на момент остановки: {active_games_count}\n\n"
                f"Для запуска используйте команду: python bot.py",
                parse_mode="Markdown",
            )
        except:
            pass

    await bot.session.close()
    logger.info("✅ Сессии закрыты")


def check_environment():
    """Проверка окружения перед запуском"""
    print("\n" + "=" * 70)
    print("🔍 ПРОВЕРКА ОКРУЖЕНИЯ")
    print("=" * 70)

    # Проверяем версию Python
    python_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    print(f"📊 Python версия: {python_version}")
    if sys.version_info.major < 3 or (
        sys.version_info.major == 3 and sys.version_info.minor < 7
    ):
        print("⚠️ Рекомендуется Python 3.7 или выше")

    # Проверяем наличие папки handlers
    if os.path.exists("handlers"):
        print("✅ Папка handlers найдена")
        required_files = [
            "__init__.py",
            "user.py",
            "admin.py",
            "http_bind.py",
            "admin_game_control.py",
            "levels.py",
        ]
        missing_files = []
        for file in required_files:
            if os.path.exists(f"handlers/{file}"):
                print(f"  ✅ {file} найден")
            else:
                print(f"  ❌ {file} НЕ НАЙДЕН!")
                missing_files.append(file)
        if missing_files:
            print(f"⚠️ Отсутствуют файлы: {', '.join(missing_files)}")
    else:
        print("❌ Папка handlers НЕ НАЙДЕНА!")
        print("   Создайте папку handlers и добавьте необходимые файлы")

    # Проверяем наличие других файлов
    print("\n📁 Проверка основных файлов:")
    required_files = [
        "donationalerts_http.py",
        "donation_polling.py",
        "keyboards.py",
        "utils.py",
        "config.py",
        "database.py",
    ]

    missing_files = []
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file} найден")
        else:
            print(f"  ❌ {file} НЕ НАЙДЕН!")
            missing_files.append(file)

    if missing_files:
        print(f"⚠️ Отсутствуют файлы: {', '.join(missing_files)}")

    # Проверяем базу данных
    if os.path.exists("dice_bot.db"):
        db_size = os.path.getsize("dice_bot.db") / 1024  # в KB
        print(f"\n✅ Файл базы данных найден (размер: {db_size:.1f} KB)")
    else:
        print("\nℹ️ База данных будет создана при первом запуске")

    # Проверяем токены
    print("\n🔐 Проверка токенов:")
    print(f"  BOT_TOKEN: {'✅ Указан' if BOT_TOKEN else '❌ НЕ УКАЗАН!'}")
    print(
        f"  DONATION_ALERTS_WIDGET_TOKEN: {'✅ Указан' if DONATION_ALERTS_WIDGET_TOKEN else '❌ НЕ УКАЗАН!'}"
    )
    print(f"  ADMIN_IDS: {ADMIN_IDS if ADMIN_IDS else '❌ НЕ УКАЗАНЫ!'}")

    # Проверка системы уровней
    print("\n🎚️ Проверка системы уровней:")
    levels = db.get_all_levels()
    if levels and len(levels) == 10:
        print(f"  ✅ Загружено {len(levels)} уровней")
        print(f"  • Начальный: {levels[0]['name']} (x{levels[0]['luck_multiplier']})")
        print(
            f"  • Максимальный: {levels[-1]['name']} (x{levels[-1]['luck_multiplier']})"
        )
    else:
        print(f"  ⚠️ Загружено {len(levels) if levels else 0} уровней (ожидалось 10)")

    print("=" * 70)
    print()


async def main():
    """Главная функция"""
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК БОТА")
    logger.info("=" * 50)

    # Информация о системе
    logger.info(f"📊 Python версия: {sys.version}")
    logger.info(f"🤖 Администраторы: {ADMIN_IDS}")
    logger.info(f"💰 Курс обмена: 1 рубль = {RUB_TO_COINS} монет")
    logger.info(f"🎮 Минимальная ставка: {MIN_BET} монет")
    logger.info(f"🎮 Максимальная ставка: {MAX_BET} монет")
    logger.info(f"👥 Реферальный бонус: +{REFERRAL_BONUS} монет")

    try:
        # Инициализация бота и диспетчера
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())

        # Регистрируем функции запуска и остановки
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        # Подключаем роутеры
        dp.include_router(user.router)
        dp.include_router(admin.router)
        dp.include_router(http_bind.router)
        dp.include_router(admin_game_control.router)
        dp.include_router(levels.router)

        logger.info("✅ Все роутеры подключены")
        logger.info("   - user.router: пользовательский интерфейс")
        logger.info("   - admin.router: админ-панель")
        logger.info("   - http_bind.router: DonationAlerts")
        logger.info("   - admin_game_control.router: управление играми")
        logger.info("   - levels.router: система уровней")

        # Устанавливаем команды бота
        await set_bot_commands(bot)

        # Пропускаем накопившиеся обновления
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Вебхуки очищены")

        # Получаем информацию о боте
        bot_info = await bot.me()
        logger.info(
            f"✅ Бот успешно инициализирован: @{bot_info.username} (ID: {bot_info.id})"
        )

        print("\n" + "=" * 80)
        print(f"✅ БОТ @{bot_info.username} УСПЕШНО ЗАПУЩЕН!")
        print("=" * 80)
        print(f"📊 Администраторы: {ADMIN_IDS}")
        print(
            f"💳 DonationAlerts Token: {'✅ Указан' if DONATION_ALERTS_WIDGET_TOKEN else '❌ Не указан'}"
        )
        print(f"💰 Курс обмена: 1 рубль = {RUB_TO_COINS} монет")
        print(f"🎚️ Система уровней: 10 уровней (макс. множитель x1.5)")
        print("=" * 80)
        print("📝 Основные команды для пользователей:")
        print("  /start - запуск бота")
        print("  /balance - баланс")
        print("  /level - система уровней")
        print("  /myid - узнать свой ID")
        print("  /top - топ игроков")
        print("=" * 80)
        print("⚙️ Команды для администраторов:")
        print("  /admin - админ-панель")
        print("  /active_games - активные игры")
        print("  /stats - статистика")
        print("=" * 80)
        print("🎮 Управление играми в реальном времени:")
        print("  • Просмотр активных игр")
        print("  • Принудительный выигрыш/проигрыш")
        print("  • Установка значения кости")
        print("  • Завершение игры")
        print("=" * 80)
        print("🎚️ Система уровней:")
        print("  • Бронзовые уровни (1-3): x1.0 - x1.1")
        print("  • Серебряные уровни (4-6): x1.15 - x1.25")
        print("  • Золотые уровни (7-9): x1.3 - x1.4")
        print("  • Бриллиантовый (10): x1.5")
        print("=" * 80)

        # Запускаем бота
        await dp.start_polling(bot)

    except TokenValidationError as e:
        logger.error(f"❌ Ошибка валидации токена: {e}")
        print("\n❌ НЕПРАВИЛЬНЫЙ ТОКЕН!")
        print("1. Проверьте токен в config.py")
        print("2. Убедитесь, что токен начинается с цифр и содержит :")
        print(
            "3. Пример правильного токена: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"
        )

    except ImportError as e:
        logger.error(f"❌ Ошибка импорта: {e}")
        print(f"\n❌ ОШИБКА ИМПОРТА: {e}")
        print("Убедитесь, что все необходимые файлы существуют")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        print(f"\n❌ ПРОИЗОШЛА КРИТИЧЕСКАЯ ОШИБКА!")
        print(f"Ошибка: {e}")
        print("Подробности смотрите в файле bot.log")

    finally:
        if "bot" in locals():
            await bot.session.close()
            logger.info("👋 Сессия бота закрыта")

        logger.info("=" * 50)
        logger.info("🛑 БОТ ОСТАНОВЛЕН")
        logger.info("=" * 50)


if __name__ == "__main__":
    try:
        # Проверяем окружение
        check_environment()

        # Если есть критические ошибки, не запускаем бота
        if not BOT_TOKEN:
            print("\n❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не указан!")
            print("Исправьте config.py и запустите бота снова")
            sys.exit(1)

        # Запускаем бота
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем (Ctrl+C)")
        logger.info("Бот остановлен пользователем")

    except SystemExit:
        print("\n👋 Бот остановлен")

    except Exception as e:
        print(f"\n❌ Необработанная ошибка: {e}")
        logger.error(f"Необработанная ошибка: {e}", exc_info=True)

    finally:
        print("\n👋 До свидания!")
