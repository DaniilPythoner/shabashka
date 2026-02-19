# donation_polling.py
import asyncio
import logging
import threading
from datetime import datetime
from typing import Optional

from config import DONATION_ALERTS_WIDGET_TOKEN, RUB_TO_COINS, ADMIN_IDS
from database import db
from donationalerts_http import DonationAlertsHTTP, da_http

logger = logging.getLogger(__name__)

class DonationPoller:
    """Класс для опроса донатов через HTTP"""
    
    def __init__(self, bot):
        self.bot = bot
        self.http_client = None
        self.running = False
        self.thread = None
        
        if not DONATION_ALERTS_WIDGET_TOKEN:
            logger.warning("⚠️ DONATION_ALERTS_WIDGET_TOKEN не указан, опрос донатов не будет запущен")
    
    def start(self):
        """Запуск опроса донатов"""
        if not DONATION_ALERTS_WIDGET_TOKEN:
            logger.warning("⚠️ Токен виджета не указан, опрос не запущен")
            return False
        
        if self.running:
            logger.warning("⚠️ Опрос уже запущен")
            return True
        
        try:
            # Создаем HTTP клиент
            self.http_client = DonationAlertsHTTP(DONATION_ALERTS_WIDGET_TOKEN)
            
            # Регистрируем обработчик
            self.http_client.on_donation(self.handle_donation)
            
            # Запускаем polling
            self.http_client.start_polling()
            self.running = True
            
            logger.info("✅ Опрос донатов запущен")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска опроса: {e}")
            return False
    
    def stop(self):
        """Остановка опроса"""
        if self.http_client:
            self.http_client.stop_polling()
        self.running = False
        logger.info("🛑 Опрос донатов остановлен")
    
    def handle_donation(self, donation_data):
        """Обработка полученного доната"""
        try:
            donation_id = donation_data['id']
            username = donation_data['username']
            amount = donation_data['amount']
            message = donation_data.get('message', '')
            currency = donation_data.get('currency', 'RUB')
            
            # Проверяем, не обрабатывали ли мы уже этот донат
            existing = self.check_donation_exists(donation_id)
            if existing:
                logger.info(f"ℹ️ Донат {donation_id} уже обработан")
                return
            
            # Конвертируем в монеты (только рубли)
            if currency != 'RUB':
                logger.info(f"ℹ️ Донат в {currency}, пропускаем (только RUB)")
                return
            
            coins = int(amount * RUB_TO_COINS)
            
            # Сохраняем в базу
            self.save_donation_to_db(donation_id, username, amount, coins, message)
            
            logger.info(f"💰 Новый донат: {username} - {amount} руб. ({coins} монет)")
            
            # Отправляем уведомление админам
            asyncio.run_coroutine_threadsafe(
                self.notify_admins(donation_data, coins),
                asyncio.get_event_loop()
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки доната: {e}")
    
    def check_donation_exists(self, donation_id: str) -> bool:
        """Проверка существования доната в БД"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM da_http_payments WHERE donation_id = ?",
                (donation_id,)
            )
            return cursor.fetchone() is not None
    
    def save_donation_to_db(self, donation_id: str, username: str, amount: float, coins: int, message: str):
        """Сохранение доната в БД"""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO da_http_payments 
                (donation_id, username, amount, coins_amount, message, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (donation_id, username, amount, coins, message, 'pending'))
            conn.commit()
    
    async def notify_admins(self, donation_data, coins):
        """Уведомление админов о новом донате"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        donation_id = donation_data['id']
        username = donation_data['username']
        amount = donation_data['amount']
        message = donation_data.get('message', '')
        
        text = (
            f"💰 **Новый донат!**\n\n"
            f"👤 Отправитель: {username}\n"
            f"💵 Сумма: {amount} руб.\n"
            f"🎁 Монет: {coins}\n"
            f"💬 Сообщение: {message or '—'}\n"
            f"🆔 ID: `{donation_id}`\n\n"
            f"⚠️ Требуется привязка к пользователю"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔗 Привязать к пользователю",
                callback_data=f"http_bind_{donation_id}"
            )],
            [InlineKeyboardButton(
                text="✅ Подтвердить без привязки",
                callback_data=f"http_confirm_{donation_id}"
            )]
        ])
        
        for admin_id in ADMIN_IDS:
            try:
                await self.bot.send_message(
                    admin_id,
                    text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления админа {admin_id}: {e}")

# Глобальный экземпляр
donation_poller = None