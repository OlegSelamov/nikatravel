
import os
import json
import logging
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def generate_test_json():
    logger.info("📦 Тестовая заглушка. Создаём filter.json")
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
    logger.info("📤 Вызываем send_to_render()")
    try:
        logger.info("📬 Подготовка к отправке filter.json")
        url = os.getenv("RENDER_API_URL")
        secret = os.getenv("RENDER_SECRET_KEY")

        logger.info(f"🔗 URL: {url}")
        logger.info(f"🔐 SECRET: {secret}")

        if not url or not secret:
            logger.error("❌ RENDER_API_URL или RENDER_SECRET_KEY не заданы")
            return

        with open("data/filter.json", "r", encoding="utf-8") as f:
            json_data = f.read()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {secret}"
        }
        response = requests.post(url, data=json_data.encode("utf-8"), headers=headers)
        logger.info(f"✅ Отправка завершена: {response.status_code} — {response.reason}")
    except Exception as e:
        logger.exception(f"❌ Ошибка в send_to_render(): {e}")
    finally:
        logger.info("✅ send_to_render() завершилась")

def run():
    logger.info("🚀 kazunion_fetch.run() запущен")
    generate_test_json()

    # Вызов только если мы точно в Railway
    if os.getenv("PLATFORM") == "railway":
        send_to_render()
    else:
        logger.info("⛔ send_to_render() не вызван — не Railway")

if __name__ == "__main__":
    run()
