# bot.py
import asyncio
import logging
import sys
import os
import threading
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.utils.token import TokenValidationError
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Импорт конфигурации
try:
    from config import BOT_TOKEN, ADMIN_IDS, DONATION_ALERTS_WIDGET_TOKEN
    from config import RUB_TO_COINS, MIN_DEPOSIT, SUPPORT_CONTACT
except ImportError as e:
    logger.error(f"❌ Ошибка импорта config.py: {e}")
    print("\n❌ ОШИБКА: Не удалось импортировать config.py")
    print(
        "Убедитесь, что файл config.py существует и содержит все необходимые настройки"
    )
    sys.exit(1)

# Проверяем наличие токена
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не указан в config.py или .env!")
    print("\n❌ ОШИБКА: BOT_TOKEN не указан!")
    print("Создайте файл .env и добавьте строку: BOT_TOKEN=ваш_токен_от_BotFather")
    sys.exit(1)

# Импорт базы данных
try:
    from database import db

    logger.info("✅ База данных подключена")
except Exception as e:
    logger.error(f"❌ Ошибка подключения к базе данных: {e}")
    print(f"\n❌ ОШИБКА: Не удалось подключиться к базе данных: {e}")
    sys.exit(1)

# Импорт обработчиков
try:
    from handlers import user, admin, http_bind

    logger.info("✅ Обработчики импортированы")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта обработчиков: {e}")
    print(f"\n❌ ОШИБКА: Не удалось импортировать обработчики: {e}")
    print("Убедитесь, что все файлы в папке handlers существуют")
    sys.exit(1)

# Импорт DonationAlerts HTTP Poller
try:
    from donation_polling import DonationPoller, donation_poller

    logger.info("✅ DonationAlerts HTTP Poller импортирован")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта donation_polling.py: {e}")
    donation_poller = None

# Импорт DonationAlerts HTTP клиента
try:
    from donationalerts_http import DonationAlertsHTTP, da_http

    logger.info("✅ DonationAlerts HTTP клиент импортирован")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта donationalerts_http.py: {e}")
    da_http = None


async def set_bot_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="help", description="📖 Помощь"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="balance", description="💰 Мой баланс"),
        BotCommand(command="top", description="🏆 Топ игроков"),
        BotCommand(command="myid", description="🆔 Мой ID"),
        BotCommand(command="admin", description="⚙️ Админ-панель"),
        BotCommand(command="support", description="📧 Поддержка"),
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
                logger.info("✅ Опрос донатов DonationAlerts запущен")
            else:
                logger.warning("⚠️ Опрос донатов не запущен")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска опроса донатов: {e}")
    else:
        logger.warning(
            "⚠️ DONATION_ALERTS_WIDGET_TOKEN не указан, опрос донатов отключен"
        )

    # Отправляем уведомление админам
    poller_status = (
        "✅ Активен" if donation_poller and donation_poller.running else "❌ Не активен"
    )
    token_status = "✅ Указан" if DONATION_ALERTS_WIDGET_TOKEN else "❌ Не указан"

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"✅ **Бот успешно запущен!**\n\n"
                f"📊 **Статус систем:**\n"
                f"• DonationAlerts Token: {token_status}\n"
                f"• HTTP Polling: {poller_status}\n"
                f"• Интервал проверки: 30 сек\n"
                f"• Курс обмена: 1 рубль = {RUB_TO_COINS} монет\n\n"
                f"🆔 Ваш ID: `{admin_id}`\n"
                f"📅 Время запуска: {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
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

    # Отправляем уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🛑 **Бот остановлен!**\n\n"
                f"📅 Время остановки: {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                f"Для запуска используйте команду: python bot.py",
                parse_mode="Markdown",
            )
        except:
            pass

    await bot.session.close()
    logger.info("✅ Сессии закрыты")


def check_environment():
    """Проверка окружения перед запуском"""
    print("\n🔍 ПРОВЕРКА ОКРУЖЕНИЯ")
    print("=" * 50)

    # Проверяем наличие .env файла
    if os.path.exists(".env"):
        print("✅ .env файл найден")
    else:
        print("⚠️ .env файл не найден, используются настройки из config.py")

    # Проверяем наличие папки handlers
    if os.path.exists("handlers"):
        print("✅ Папка handlers найдена")
        required_files = ["__init__.py", "user.py", "admin.py", "http_bind.py"]
        for file in required_files:
            if os.path.exists(f"handlers/{file}"):
                print(f"  ✅ {file} найден")
            else:
                print(f"  ❌ {file} НЕ НАЙДЕН!")
    else:
        print("❌ Папка handlers НЕ НАЙДЕНА!")

    # Проверяем наличие других файлов
    required_files = [
        "donationalerts_http.py",
        "donation_polling.py",
        "keyboards.py",
        "utils.py",
    ]

    print("\n📁 Проверка основных файлов:")
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file} найден")
        else:
            print(f"  ❌ {file} НЕ НАЙДЕН!")

    # Проверяем базу данных
    if os.path.exists("dice_bot.db"):
        print("\n✅ Файл базы данных найден")
    else:
        print("\nℹ️ База данных будет создана при первом запуске")

    # Проверяем токены
    print("\n🔐 Проверка токенов:")
    print(f"  BOT_TOKEN: {'✅ Указан' if BOT_TOKEN else '❌ НЕ УКАЗАН!'}")
    print(
        f"  DONATION_ALERTS_WIDGET_TOKEN: {'✅ Указан' if DONATION_ALERTS_WIDGET_TOKEN else '❌ НЕ УКАЗАН!'}"
    )
    print(f"  ADMIN_IDS: {ADMIN_IDS}")

    print("=" * 50)
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

        logger.info("✅ Все роутеры подключены")

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

        print("\n" + "=" * 60)
        print(f"✅ БОТ @{bot_info.username} УСПЕШНО ЗАПУЩЕН!")
        print("=" * 60)
        print(f"📊 Администраторы: {ADMIN_IDS}")
        print(
            f"💳 DonationAlerts Token: {'✅ Указан' if DONATION_ALERTS_WIDGET_TOKEN else '❌ Не указан'}"
        )
        print(f"💰 Курс обмена: 1 рубль = {RUB_TO_COINS} монет")
        print("=" * 60)
        print("📝 Основные команды:")
        print("  /start - запуск бота")
        print("  /admin - админ-панель")
        print("  /balance - баланс")
        print("=" * 60)

        # Запускаем бота
        await dp.start_polling(bot)

    except TokenValidationError as e:
        logger.error(f"❌ Ошибка валидации токена: {e}")
        print("\n❌ НЕПРАВИЛЬНЫЙ ТОКЕН!")
        print("1. Проверьте токен в .env файле")
        print("2. Убедитесь, что токен начинается с цифр и содержит :")
        print(
            "3. Пример правильного токена: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890"
        )

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
