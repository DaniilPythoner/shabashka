# bot.py
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.utils.token import TokenValidationError

from config import BOT_TOKEN
from database import db
from handlers import user, admin, bank_payments

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="profile", description="Мой профиль"),
        BotCommand(command="balance", description="Мой баланс"),
        BotCommand(command="top", description="Топ игроков"),
        BotCommand(command="myid", description="Мой ID и статус"),
        BotCommand(command="admin", description="Админ-панель"),
        BotCommand(command="debug_admin", description="Отладка админа"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("✅ Команды бота установлены")
    except Exception as e:
        logger.error(f"❌ Ошибка при установке команд: {e}")


async def main():
    """Главная функция"""
    logger.info("🚀 Запуск бота...")

    # Проверяем токен
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не указан в config.py или .env!")
        print("\n❌ ОШИБКА: BOT_TOKEN не указан!")
        print("Создайте файл .env и добавьте строку: BOT_TOKEN=ваш_токен")
        return

    try:
        # Инициализация бота и диспетчера
        bot = Bot(token=BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())

        # Подключаем роутеры
        dp.include_router(user.router)
        dp.include_router(admin.router)
        dp.include_router(bank_payments.router)

        # Устанавливаем команды
        await set_bot_commands(bot)

        # Пропускаем накопившиеся обновления
        await bot.delete_webhook(drop_pending_updates=True)

        bot_info = await bot.me()
        logger.info(f"✅ Бот успешно инициализирован! @{bot_info.username}")

        # Запускаем бота
        await dp.start_polling(bot)

    except TokenValidationError as e:
        logger.error(f"❌ Ошибка валидации токена: {e}")
        print("\n❌ НЕПРАВИЛЬНЫЙ ТОКЕН!")
        print("Проверьте токен в .env файле")

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print(f"\n❌ Произошла ошибка: {e}")

    finally:
        if "bot" in locals():
            await bot.session.close()
            logger.info("👋 Сессия бота закрыта")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
