
from bs4 import BeautifulSoup
import json
import logging
import os
import re
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = Path(BASE_DIR) / "data"

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)
LOG_FILE = os.path.join(BASE_DIR, "parser.log")
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(file_handler)

# Найдем последнюю папку html_*
html_folders = [p for p in DATA_DIR.glob("html_*") if p.is_dir()]
if not html_folders:
    raise FileNotFoundError("❌ Не найдена ни одна папка html_*")
last_folder = max(html_folders, key=os.path.getmtime)
logger.info(f"📂 Парсим HTML из папки: {last_folder}")

# Лимит
try:
    with open(DATA_DIR / "kazunion_config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        limit = int(config.get("limit")) if str(config.get("limit")).isdigit() else None
except Exception:
    limit = None

# Загружаем существующие данные
existing_data = {}
filter_path = DATA_DIR / "filter.json"
if filter_path.exists():
    try:
        with open(filter_path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        for hotel in old_data:
            existing_data[hotel["hotel"].strip().lower()] = hotel
    except Exception as e:
        logger.warning(f"⚠️ Ошибка чтения filter.json: {e}")

hotels_data = existing_data.copy()
html_files = sorted(last_folder.glob("kazunion_page_*.html"))
logger.info(f"🔍 Найдено {len(html_files)} HTML-файлов для парсинга")

for html_file in html_files:
    logger.info(f"📄 Парсим файл: {html_file}")
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    rows = soup.find_all("tr")
    for row in rows:
        tds = row.find_all("td")
        if len(tds) < 14:
            continue
        try:
            date_raw = tds[1].get_text(strip=True)
            country_city_raw = tds[2].get_text(strip=True)
            nights_raw = tds[3].get_text(strip=True)

            # Если две цифры подряд, суммируем
            if len(nights_raw) == 2 and nights_raw.isdigit():
                nights = str(int(nights_raw[0]) + int(nights_raw[1]))
            else:
                nights = nights_raw
                
            hotel_name_raw = tds[4].get_text(strip=True)
            hotel_key = hotel_name_raw.strip().lower()
            seats = tds[5].get_text(strip=True)
            # Берём текст из колонки "Питание"
            meal_raw = tds[6].get_text(strip=True).upper()

            # Маппинг для нормализации
            meal_map = {
                "AI": "AI",
                "ALL INCLUSIVE": "AI",
                "BB": "BB",
                "BED & BREAKFAST": "BB",
                "FB": "FB",
                "FULL BOARD": "FB",
                "HB": "HB",
                "HALF BOARD": "HB",
                "RO": "RO",
                "ROOM ONLY": "RO",
                "UAI": "UAI",
                "ULTRA ALL INCLUSIVE": "UAI"
            }

            # Находим нормализованное значение
            meal = meal_map.get(meal_raw, "BB")
            price_raw = tds[10].get_text(strip=True)

            if not date_raw or not hotel_name_raw or not price_raw or "KZT" not in price_raw:
                continue
            parts = country_city_raw.split(" из ")
            if len(parts) != 2:
                continue

            destination_raw, departure_city_raw = parts

            # Чистим город вылета
            city = re.sub(r"\s*\(.*?\)", "", departure_city_raw)  # убираем (Air Astana) и т.п.
            city = re.sub(r"(Air\s*Astana|SPO\s*NEW|SPO|FN|Standard)", "", city, flags=re.IGNORECASE)  # убираем пометки
            city = re.sub(r"[.,\-]", "", city)  # убираем точки, запятые и дефисы
            city = re.sub(r"\d+", "", city)  # убираем цифры
            city = re.sub(r"[A-Za-z]+", "", city)  # убираем латиницу (bef7 и прочее)
            city = re.sub(r"\s+", " ", city).strip()  # убираем лишние пробелы

            # Чистим страну
            destination_clean = re.sub(r"\s*\(.*?\)", "", destination_raw)  # убираем (Пхукет)
            destination_clean = destination_clean.split("+")[0]  # убираем всё после "+"
            destination_clean = re.sub(r"[.,\-]", "", destination_clean)  # убираем точки, запятые и дефисы
            destination_clean = re.sub(r"\d+", "", destination_clean)  # убираем цифры
            destination_clean = re.sub(r"[A-Za-z]+", "", destination_clean)  # убираем латиницу
            destination_clean = re.sub(r"\s+", " ", destination_clean).strip()

            destination_to_country = {
                # Азербайджан
                "Азербайджан": "Азербайджан",
                # Вьетнам
                "Дананг": "Вьетнам",
                "Нячанг": "Вьетнам",
                "Хойан": "Вьетнам",
                "Камрань": "Вьетнам",
                "Хюэ": "Вьетнам",
                "Фукуок": "Вьетнам",
                "Хошимин": "Вьетнам",
                # Грузия
                "Аджария-Батуми": "Грузия",
                "Бакуриани": "Грузия",
                "Боржоми": "Грузия",
                "Гудаури": "Грузия",
                "Гурия-Уреки": "Грузия",
                "Имерети-Кутаиси": "Грузия",
                "Кахетия": "Грузия",
                "Саирме": "Грузия",
                "Сванетия": "Грузия",
                "Тбилиси": "Грузия",
                # Индонезия
                "Бали": "Индонезия",
                # Катар
                "Доха": "Катар",
                # Малайзия
                "Куала-Лумпур": "Малайзия",
                "Пинанг": "Малайзия",
                # Мальдивы
                "Мальдивы": "Мальдивы",
                # ОАЭ
                "Дубай": "ОАЭ",
                "Абу-Даби": "ОАЭ",
                "Шарджа": "ОАЭ",
                "Аджман": "ОАЭ",
                "Аль-Айн": "ОАЭ",
                "Рас Аль Хайма": "ОАЭ",
                "Ум Аль Кувейн": "ОАЭ",
                "Фуджейра": "ОАЭ",
                # Сингапур
                "Сингапур": "Сингапур",
                # Словения
                "Словения": "Словения",
                # Таиланд
                "Пхукет": "Таиланд",
                "Бангкок": "Таиланд",
                "Самуи": "Таиланд",
                "Као Лак": "Таиланд",
                "Ко Чанг": "Таиланд",
                "Краби": "Таиланд",
                "Паттайя": "Таиланд",
                "Пханг Нга": "Таиланд",
                "Районг": "Таиланд",
                "Самед": "Таиланд",
                "Самуи": "Таиланд",
                # Турция
                "Алания": "Турция",
                "Анталья": "Турция",
                "Белек": "Турция",
                "Бодрум": "Турция",
                "Дидим": "Турция",
                "Каш": "Турция",
                "Кемер": "Турция",
                "Кушадасы": "Турция",
                "Мармарис": "Турция",
                "Сиде": "Турция",
                "Стамбул": "Турция",
                "Фетхие": "Турция",
                "Экскурсионные Туры": "Турция",
                # Черногория
                "Черногория": "Черногория",
                # Чехия
                "Карловы Вары": "Чехия",
                "Марианские Лазне": "Чехия",
                "Прага": "Чехия",
                "Теплице": "Чехия",
                "Яхимов": "Чехия",
                # Шри-Ланка
                "Шри-Ланка": "Шри-Ланка",
                # Южная Корея
                "Корея": "Южная Корея",
                "Сеул": "Южная Корея"
            }

            country = destination_to_country.get(destination_clean, destination_clean)

            price = price_raw.replace(" KZT", "").replace(" ", "")
            date = date_raw.split(",")[0]

            if hotel_key not in hotels_data:
                hotels_data[hotel_key] = {
                    "hotel": hotel_name_raw,
                    "city": city,
                    "country": country,
                    "meal": meal,
                    "nights": nights,
                    "seats": seats if seats else "-",
                    "price": price,
                    "old_price": "",
                    "discount_percent": "",
                    "price_per_month": "",
                    "installment_months": "",
                    "image": "",
                    "gallery": [],
                    "description": "",
                    "dates_prices": []
                }
                try:
                    price_int = int(price)
                    old_price = round(price_int / 0.8)
                    final_price = round(price_int * 1.12)
                    price_per_month = round(final_price / 12)
                    hotels_data[hotel_key]["old_price"] = str(old_price)
                    hotels_data[hotel_key]["discount_percent"] = "20"
                    hotels_data[hotel_key]["installment_months"] = "12"
                    hotels_data[hotel_key]["price_per_month"] = str(price_per_month)
                except Exception as e:
                    logger.info(f"⚠️ Ошибка при расчёте цены: {e}")

            # Добавляем дату и цену, если такой даты еще нет
            if not any(dp["date"] == date for dp in hotels_data[hotel_key]["dates_prices"]):
                hotels_data[hotel_key]["dates_prices"].append({"date": date, "price": price})
                logger.info(f"➕ Отель: {hotel_name_raw} | Дата: {date} | Цена: {price}")

        except Exception as e:
            logger.warning(f"⚠️ Ошибка при обработке строки: {e}")
            continue

def normalize_hotel_name(name):
    return re.sub(r"[^a-zA-Zа-яА-Я0-9]", "", name.lower())

# Загружаем существующий filter.json
existing_data = {}
if filter_path.exists():
    try:
        with open(filter_path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        for hotel in old_data:
            key = normalize_hotel_name(hotel.get("hotel", ""))
            existing_data[key] = hotel
    except Exception as e:
        logger.warning(f"⚠️ Ошибка чтения filter.json: {e}")

# Сливаем новые данные
for key, new_hotel in hotels_data.items():
    norm_key = normalize_hotel_name(new_hotel.get("hotel", ""))
    if norm_key in existing_data:
        existing = existing_data[norm_key]
        # Обновляем только даты и цены
        for dp in new_hotel["dates_prices"]:
            if not any(x["date"] == dp["date"] for x in existing.get("dates_prices", [])):
                existing.setdefault("dates_prices", []).append(dp)
        existing["price"] = new_hotel["price"]
        existing["old_price"] = new_hotel["old_price"]
        existing["discount_percent"] = new_hotel["discount_percent"]
        existing["price_per_month"] = new_hotel["price_per_month"]
        existing["installment_months"] = new_hotel["installment_months"]
    else:
        existing_data[norm_key] = new_hotel
        logger.info(f"➕ Добавлен новый отель: {new_hotel['hotel']}")

final_results = list(existing_data.values())

# Проставим уникальные ID
existing_ids = set()
for item in existing_data.values():
    if "id" in item:
        existing_ids.add(item["id"])

next_id = max(existing_ids, default=0) + 1

# Присваиваем ID, если его нет
for hotel in final_results:
    if "id" not in hotel or not isinstance(hotel["id"], int):
        hotel["id"] = next_id
        next_id += 1

with open(filter_path, "w", encoding="utf-8") as f:
    json.dump(final_results, f, indent=2, ensure_ascii=False)

logger.info(f"✅ Сформировано {len(final_results)} туров (объединено по отелям).")
print(f"Готово: {len(final_results)} туров сохранено в filter.json")