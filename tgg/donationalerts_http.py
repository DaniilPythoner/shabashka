# donationalerts_http.py
import requests
import time
import threading
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable

logger = logging.getLogger(__name__)

class DonationAlertsHTTP:
    """Класс для работы с DonationAlerts через HTTP запросы (без OAuth и socketio)"""
    
    def __init__(self, widget_token: str):
        """
        Инициализация с токеном виджета
        Токен можно получить в настройках профиля DonationAlerts -> "Показать токен"
        """
        self.widget_token = widget_token
        self.last_check = None
        self.last_donation_id = None
        self.donation_callbacks = []
        self.running = False
        self.check_interval = 30  # Проверка каждые 30 секунд
        self.thread = None
        
        # Сессия для запросов
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.widget_token}',
            'User-Agent': 'Mozilla/5.0 (compatible; TelegramBot/1.0)'
        })
        
        logger.info("✅ DonationAlerts HTTP инициализирован")
    
    def get_donations(self, limit: int = 10) -> Optional[List[Dict]]:
        """
        Получение списка последних донатов через API
        Использует публичный API DonationAlerts
        """
        try:
            # Используем публичный API для получения донатов
            url = "https://www.donationalerts.com/api/v1/alerts/donations"
            params = {
                'limit': limit,
                'type': 'donation'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                donations = data.get('data', [])
                logger.debug(f"Получено {len(donations)} донатов")
                return donations
            else:
                logger.error(f"Ошибка получения донатов: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("Таймаут при запросе к DonationAlerts")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Ошибка подключения к DonationAlerts")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении донатов: {e}")
            return None
    
    def get_donations_since(self, since_id: Optional[str] = None, minutes: int = 60) -> List[Dict]:
        """
        Получение донатов за последние N минут или с определенного ID
        """
        all_donations = self.get_donations(limit=50)
        if not all_donations:
            return []
        
        # Фильтруем по времени
        filtered = []
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        for donation in all_donations:
            # Проверяем по ID
            if since_id and donation.get('id') == since_id:
                break
            
            # Проверяем по времени
            created_at = donation.get('created_at', '')
            if created_at:
                try:
                    don_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if don_time > cutoff_time:
                        filtered.append(donation)
                except:
                    filtered.append(donation)
            else:
                filtered.append(donation)
        
        return filtered
    
    def check_new_donations(self):
        """Проверка новых донатов"""
        try:
            # Получаем последние донаты
            donations = self.get_donations(limit=5)
            if not donations:
                return
            
            # Обрабатываем новые донаты
            for donation in donations:
                donation_id = donation.get('id')
                
                # Пропускаем уже обработанные
                if self.last_donation_id and donation_id <= self.last_donation_id:
                    continue
                
                # Извлекаем данные
                donation_data = {
                    'id': donation_id,
                    'username': donation.get('username', 'Аноним'),
                    'amount': float(donation.get('amount', 0)),
                    'amount_formatted': donation.get('amount_formatted', '0'),
                    'currency': donation.get('currency', 'RUB'),
                    'message': donation.get('message', ''),
                    'created_at': donation.get('created_at', ''),
                    'is_test': donation.get('is_test', False)
                }
                
                # Пропускаем тестовые донаты
                if donation_data['is_test']:
                    logger.info(f"🧪 Тестовый донат от {donation_data['username']}")
                    continue
                
                logger.info(f"💰 Новый донат: {donation_data['username']} - {donation_data['amount_formatted']} {donation_data['currency']}")
                
                # Вызываем колбэки
                for callback in self.donation_callbacks:
                    try:
                        callback(donation_data)
                    except Exception as e:
                        logger.error(f"Ошибка в колбэке: {e}")
                
                # Обновляем последний ID
                if not self.last_donation_id or donation_id > self.last_donation_id:
                    self.last_donation_id = donation_id
            
            self.last_check = datetime.now()
            
        except Exception as e:
            logger.error(f"Ошибка при проверке донатов: {e}")
    
    def start_polling(self):
        """Запуск периодической проверки в фоновом потоке"""
        if self.running:
            logger.warning("⚠️ Polling уже запущен")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()
        logger.info(f"✅ Polling запущен (интервал: {self.check_interval} сек)")
    
    def _polling_loop(self):
        """Основной цикл проверки"""
        while self.running:
            try:
                self.check_new_donations()
            except Exception as e:
                logger.error(f"Ошибка в цикле polling: {e}")
            
            # Ждем перед следующей проверкой
            time.sleep(self.check_interval)
    
    def stop_polling(self):
        """Остановка проверки"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("🛑 Polling остановлен")
    
    def on_donation(self, callback: Callable[[Dict], None]):
        """Регистрация обработчика донатов"""
        self.donation_callbacks.append(callback)
    
    def get_balance(self) -> Optional[float]:
        """Получение текущего баланса (требует OAuth, может не работать)"""
        try:
            # Этот метод может не работать без OAuth
            url = "https://www.donationalerts.com/api/v1/user/balance"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('balance', 0)
            else:
                logger.warning(f"Не удалось получить баланс: {response.status_code}")
                return None
        except:
            return None

# Глобальный экземпляр
da_http = None