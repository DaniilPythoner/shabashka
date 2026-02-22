# donationalerts.py
import aiohttp
import time
from typing import Optional, Dict, Any


class DonationAlertsAPI:
    """Класс для работы с API DonationAlerts (только создание платежей)"""

    BASE_URL = "https://www.donationalerts.com/api/v1"

    def __init__(self, token: str = None, wallet_id: str = None):
        self.token = token
        self.wallet_id = wallet_id

        if not self.token:
            print("⚠️ ВНИМАНИЕ: DonationAlerts токен не указан!")

    async def create_payment(
        self, amount: float, description: str = "Пополнение баланса"
    ) -> Optional[Dict[str, Any]]:
        """
        Создание платежа через DonationAlerts
        Возвращает URL для оплаты и ID платежа
        """
        if not self.token:
            return None

        url = f"{self.BASE_URL}/payment/create"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Генерируем уникальный ID заказа
        order_id = f"order_{int(time.time())}"

        payload = {
            "wallet_id": self.wallet_id,
            "amount": amount,
            "description": description,
            "custom": order_id,
            "redirect_url": "https://t.me/@shabashkadice_bot",  # Замените на username вашего бота
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "payment_url": data.get("url"),
                            "payment_id": data.get("id"),
                            "order_id": order_id,
                        }
                    else:
                        error_text = await response.text()
                        print(
                            f"Ошибка создания платежа: {response.status} - {error_text}"
                        )
                        return None
        except Exception as e:
            print(f"Исключение при создании платежа: {e}")
            return None


# Создаем глобальный экземпляр
from config import DONATION_ALERTS_TOKEN, DONATION_ALERTS_WALLET_ID

donationalerts = DonationAlertsAPI(DONATION_ALERTS_TOKEN, DONATION_ALERTS_WALLET_ID)
