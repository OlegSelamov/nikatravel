from bs4 import BeautifulSoup
import json
import sys
import io
import logging
import os

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "parser.log")

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(file_handler)

# Читаем лимит из конфигурации
try:
    with open("data/kazunion_config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        limit = config.get("limit")
        if isinstance(limit, str) and limit.isdigit():
            limit = int(limit)
except Exception:
    limit = None

# Парсим HTML
with open("data/kazunion_result.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

rows = soup.find_all("tr")
results = []

for row in rows:
    tds = row.find_all("td")
    if len(tds) < 14:
        continue

    try:
        date_raw = tds[1].get_text(strip=True)
        country_city_raw = tds[2].get_text(strip=True)
        nights = tds[3].get_text(strip=True)

        if nights.isdigit() and int(nights) >= 30 and len(nights) == 2:
            fixed = int(nights[0]) + int(nights[1])
            nights = str(fixed)

        hotel = tds[4].get_text(strip=True)
        seats = tds[5].get_text(strip=True)
        meal = tds[6].get_text(strip=True)
        price_raw = tds[10].get_text(strip=True)

        if not date_raw or not hotel or not price_raw or "KZT" not in price_raw:
            continue

        country_city_parts = country_city_raw.split(" из ")
        if len(country_city_parts) != 2:
            continue

        country, city = country_city_parts
        price = price_raw.replace(" KZT", "").replace(" ", "")

        tour = {
            "departure_date": date_raw.split(",")[0],
            "city": city,
            "country": country,
            "hotel": hotel,
            "nights": nights,
            "meal": meal,
            "seats": seats if seats else "-",
            "price": price,
            "old_price": "",
            "discount_percent": "",
            "price_per_month": "",
            "installment_months": "",
            "image": "",
            "gallery": [],
            "description": ""
        }

        results.append(tour)

        # автоматически считаем скидку, старую цену и рассрочку
        try:
            price_int = int(price)
            old_price = round(price_int / 0.8)
            final_price = round(price_int * 1.12)
            price_per_month = round(final_price / 12)

            tour["old_price"] = str(old_price)
            tour["discount_percent"] = "20"
            tour["installment_months"] = "12"
            tour["price_per_month"] = str(price_per_month)
        except Exception as e:
            logger.info(f"⚠️ Ошибка при расчёте цены: {e}")

    except Exception:
        continue

# применяем лимит
if limit:
    results = results[:limit]

# сохраняем без затирания старых данных
try:
    with open("data/filter.json", "r", encoding="utf-8") as f:
        existing = json.load(f)
except Exception:
    existing = []
    
    # Исключаем дубликаты по дате, городу, стране и отелю
def is_duplicate(new_tour, existing):
    for tour in existing:
        if (
            tour["departure_date"] == new_tour["departure_date"]
            and tour["city"] == new_tour["city"]
            and tour["country"] == new_tour["country"]
            and tour["hotel"] == new_tour["hotel"]
        ):
            return True
    return False

results = [r for r in results if not is_duplicate(r, existing)]

existing.extend(results)

with open("data/filter.json", "w", encoding="utf-8") as f:
    json.dump(existing, f, indent=2, ensure_ascii=False)

logger.info(f"✅ Добавлено {len(results)} новых записей. Всего теперь: {len(existing)}")