
import os
import json
import logging
import requests
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def generate_test_json():
    logging.info("📦 Тестовая заглушка. Создаём filter.json")
    test_data = [{
        "departure_date": datetime.now().strftime("%Y-%m-%d"),
        "city": "Алматы",
        "country": "Турция",
        "hotel": "Test Hotel",
        "nights": "7",
        "meal": "AI",
        "seats": "Есть",
        "price": "500000",
        "description": "Тестовый тур для отладки.",
        "image": "test.jpg",
        "old_price": "600000",
        "discount_percent": "17",
        "price_per_month": "20833",
        "installment_months": "24"
    }]
    Path("data").mkdir(exist_ok=True)
    with open("data/filter.json", "w", encoding="utf-8") as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

def send_to_render():
    import requests, os, logging
    url = os.getenv("RENDER_API_URL")
    secret = os.getenv("RENDER_SECRET_KEY")
    
    logging.info(f"📬 Подготовка к отправке filter.json")
    logging.info(f"🔗 URL: {url}")
    logging.info(f"🔐 SECRET: {secret}")
    
    if not url or not secret:
        logging.error("❌ RENDER_API_URL или RENDER_SECRET_KEY не заданы")
        return

    headers = {"Authorization": f"Bearer {secret}"}
    try:
        with open("data/filter.json", "rb") as f:
            response = requests.post(url, data=f, headers=headers)
        logging.info(f"✅ Отправка завершена: {response.status_code} — {response.text}")
    except Exception as e:
        logging.error(f"💥 Ошибка при отправке: {e}")

def run():
    logging.info("🚀 kazunion_fetch.run() запущен")
    generate_test_json()

    # Вызов только если мы точно в Railway
    if os.getenv("PLATFORM") == "railway":
        send_to_render()
    else:
        logging.info("⛔ send_to_render() не вызван — не Railway")

if __name__ == "__main__":
    run()
