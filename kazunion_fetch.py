import os
import json
import logging
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def send_to_render():
    logger.info("📬 Подготовка к отправке filter.json")

    render_url = os.getenv("RENDER_API_URL")
    secret_key = os.getenv("RENDER_SECRET_KEY")

    logger.info(f"🔗 URL: {render_url}")
    logger.info(f"🔐 SECRET: {secret_key}")

    if not render_url or not secret_key:
        logger.error("❌ RENDER_API_URL или RENDER_SECRET_KEY не заданы")
        return

    try:
        with open("data/filter.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        response = requests.post(
            render_url,
            headers={"Authorization": f"Bearer {secret_key}"},
            json=data,
            timeout=20
        )

        logger.info(f"✅ Отправка завершена: {response.status_code} — {response.text}")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке на сайт: {e}")

def run():
    logger.info("🚀 kazunion_fetch.run() запущен")
    try:
        logger.info("📦 Тестовая заглушка. Создаём filter.json")

        test_data = [{
            "image": "default.jpg",
            "hotel": "Test Hotel",
            "country": "Тестляндия",
            "price": "100000",
            "old_price": "120000",
            "discount_percent": "17",
            "price_per_month": "4166",
            "installment_months": "24",
            "departure_date": "2025-08-01",
            "city": "Алматы",
            "nights": "7",
            "meal": "AI",
            "seats": "Есть",
            "description": "Тестовый тур"
        }]

        os.makedirs("data", exist_ok=True)
        with open("data/filter.json", "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)

        logger.info("📤 Вызываем send_to_render()")
        send_to_render()
        logger.info("✅ send_to_render() завершилась")

    except Exception as e:
        logger.error(f"💥 Ошибка в run(): {e}")

if __name__ == "__main__":
    run()