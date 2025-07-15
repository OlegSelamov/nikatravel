import subprocess
import os
import json
import logging
import requests,os
import threading
from flask import Flask, request
from datetime import datetime
from pathlib import Path

# Настройка логов — лог-файл общий
logging.basicConfig(
    filename="parser.log",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

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
    url = os.getenv("RENDER_API_URL")
    secret = os.getenv("RENDER_SECRET_KEY")

    if not url or not secret:
        logging.error("❌ RENDER_API_URL или RENDER_SECRET_KEY не заданы")
        return

    try:
        with open("data/filter.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        headers = {
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=data)

        logging.info(f"✅ Отправка завершена: {response.status_code} — {response.text}")

    except Exception as e:
        logging.error(f"❌ Ошибка при отправке в Render: {e}")

def run():
    logging.info("🚀 kazunion_fetch.run() запущен")
    generate_test_json()

    # Вызов только если мы точно в Railway
    if os.getenv("PLATFORM") == "railway":
        send_to_render()
    else:
        logging.info("⛔ send_to_render() не вызван — не Railway")

app = Flask(__name__)

@app.route('/run', methods=['POST'])
def remote_trigger():
    auth = request.headers.get("Authorization")
    if auth != f"Bearer {os.getenv('RAILWAY_SECRET')}":
        logging.warning("⛔ Неверный токен доступа к /run")
        return "Forbidden", 403

    def background_task():
        logging.info("🚀 kazunion_fetch.run() запущен удалённо")
        subprocess.run(["python", "kazunion_fetch.py"])

    threading.Thread(target=background_task).start()
    return "Парсинг запущен", 200


port = int(os.environ.get("PORT", 8080))
app.run(host="0.0.0.0", port=port)


