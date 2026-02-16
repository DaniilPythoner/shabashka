# quick_fix.py
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

print("🔧 БЫСТРОЕ ИСПРАВЛЕНИЕ АДМИН-ПАНЕЛИ\n")

# Получаем ID из .env или запрашиваем
admin_ids_str = os.getenv("ADMIN_IDS", "")
admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

if admin_ids:
    print(f"Найдены ADMIN_IDS из .env: {admin_ids}")
    your_id = admin_ids[0]
    print(f"Используем первый ID: {your_id}")
else:
    your_id = int(input("Введите ваш Telegram ID: "))

# Подключаемся к базе
conn = sqlite3.connect("dice_bot.db")
cursor = conn.cursor()

# Проверяем, есть ли пользователь
cursor.execute("SELECT * FROM users WHERE user_id = ?", (your_id,))
user = cursor.fetchone()

if user:
    print(f"✅ Пользователь {your_id} найден в базе")

    # Назначаем админом
    cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (your_id,))
    conn.commit()
    print(f"✅ Пользователь {your_id} назначен администратором в БД!")
else:
    print(f"❌ Пользователь {your_id} не найден в базе!")

    # Добавляем пользователя
    cursor.execute(
        """
        INSERT INTO users (user_id, username, first_name, balance, is_admin) 
        VALUES (?, ?, ?, ?, ?)
    """,
        (your_id, "admin", "Admin", 10000, 1),
    )
    conn.commit()
    print(f"✅ Пользователь {your_id} создан и назначен администратором!")

# Проверяем результат
cursor.execute(
    "SELECT user_id, username, is_admin FROM users WHERE user_id = ?", (your_id,)
)
updated = cursor.fetchone()
print(f"\n📊 Результат: ID={updated[0]}, Username={updated[1]}, is_admin={updated[2]}")

conn.close()

print("\n✅ ГОТОВО! Теперь перезапустите бота.")
print("📝 Используйте команду /admin для открытия админ-панели")
