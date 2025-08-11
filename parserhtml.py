from bs4 import BeautifulSoup
import json
import logging
import os
import re
from pathlib import Path
from datetime import datetime

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

# ----------------------- УТИЛИТЫ НОРМАЛИЗАЦИИ/КЛЮЧА -----------------------

def normalize_str(x):
    if x is None:
        return ""
    s = str(x).strip()
    s = " ".join(s.split())
    return s.lower()

def parse_date_any(s):
    s = str(s).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    # если попалось "13.08.2025, ср" — отрежем всё после первой запятой и ещё раз
    s2 = s.split(",", 1)[0].strip()
    if s2 != s:
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(s2, fmt)
            except ValueError:
                pass
    raise ValueError(f"Не удалось распарсить дату: {s}")

def date_to_standard_str(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y")

def normalize_date_to_standard(s):
    try:
        return date_to_standard_str(parse_date_any(s))
    except Exception:
        return None

def make_key(rec: dict) -> str:
    """Ключ сопоставления тура: страна|город|отель|питание|ночей"""
    return "|".join([
        normalize_str(rec.get("country", "")),
        normalize_str(rec.get("city", "")),
        normalize_str(rec.get("hotel", "")),
        normalize_str(rec.get("meal", "")),
        normalize_str(rec.get("nights", "")),
    ])

def recompute_primary_price(rec: dict) -> None:
    """Пересчитываем rec['price'] как минимальную цену из dates_prices (если есть)."""
    dps = rec.get("dates_prices") or []
    prices = []
    for x in dps:
        p = str(x.get("price", "")).replace(" ", "")
        if p.isdigit():
            prices.append(int(p))
    if prices:
        rec["price"] = str(min(prices))

# ----------------------- НАХОДИМ ПОСЛЕДНЮЮ ПАПКУ HTML -----------------------

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

# ----------------------- ЗАГРУЗКА СУЩЕСТВУЮЩИХ ДАННЫХ -----------------------

filter_path = DATA_DIR / "filter.json"

def ensure_dates_prices_standard(rec: dict) -> None:
    """Приводим dates_prices к единому формату и убираем битые даты."""
    dps = rec.get("dates_prices") or []
    std = []
    for dp in dps:
        if not isinstance(dp, dict):
            continue
        d = normalize_date_to_standard(dp.get("date"))
        if not d:
            continue
        std.append({"date": d, "price": str(dp.get("price", ""))})
    rec["dates_prices"] = std

existing_list = []
if filter_path.exists():
    try:
        with open(filter_path, "r", encoding="utf-8") as f:
            existing_list = json.load(f)
        if not isinstance(existing_list, list):
            existing_list = []
    except Exception as e:
        logger.warning(f"⚠️ Ошибка чтения filter.json: {e}")
        existing_list = []

# Индекс существующих туров по сложному ключу
existing_index = {}
for rec in existing_list:
    ensure_dates_prices_standard(rec)
    existing_index[make_key(rec)] = rec

# ----------------------- ПАРСИНГ HTML -----------------------

hotels_parsed = []  # будем складывать свежие записи перед мерджем
html_files = sorted(last_folder.glob("kazunion_page_*.html"))
logger.info(f"🔍 Найдено {len(html_files)} HTML-файлов для парсинга")

count_added_rows = 0

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

            # Если две цифры подряд, суммируем (наследуем твоё правило)
            if len(nights_raw) == 2 and nights_raw.isdigit():
                nights = str(int(nights_raw[0]) + int(nights_raw[1]))
            else:
                nights = nights_raw

            hotel_name_raw = tds[4].get_text(strip=True)
            seats = tds[5].get_text(strip=True)

            meal_raw = tds[6].get_text(strip=True).upper()
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
            meal = meal_map.get(meal_raw, "BB")

            price_raw = tds[10].get_text(strip=True)

            if not date_raw or not hotel_name_raw or not price_raw or "KZT" not in price_raw:
                continue
            parts = country_city_raw.split(" из ")
            if len(parts) != 2:
                continue

            destination_raw, departure_city_raw = parts

            # Чистим город вылета
            city = re.sub(r"\s*\(.*?\)", "", departure_city_raw)
            city = re.sub(r"(Air\s*Astana|SPO\s*NEW|SPO|FN|Standard)", "", city, flags=re.IGNORECASE)
            city = re.sub(r"[.,\-]", "", city)
            city = re.sub(r"\d+", "", city)
            city = re.sub(r"[A-Za-z]+", "", city)
            city = re.sub(r"\s+", " ", city).strip()

            # Чистим страну/направление
            destination_clean = re.sub(r"\s*\(.*?\)", "", destination_raw)
            destination_clean = destination_clean.split("+")[0]
            destination_clean = re.sub(r"[.,\-]", "", destination_clean)
            destination_clean = re.sub(r"\d+", "", destination_clean)
            destination_clean = re.sub(r"[A-Za-z]+", "", destination_clean)
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
            date_std = normalize_date_to_standard(date_raw)
            if not date_std:
                continue

            rec_new = {
                "hotel": hotel_name_raw,
                "city": city,
                "country": country,
                "meal": meal,
                "nights": nights,
                "seats": seats if seats else "-",
                "price": price,  # пересчёт ниже возможен
                "old_price": "",
                "discount_percent": "",
                "price_per_month": "",
                "installment_months": "",
                "image": "",
                "gallery": [],
                "description": "",
                "dates_prices": [{"date": date_std, "price": price}],
            }

            # Расчёты цен (как у тебя было)
            try:
                price_int = int(price)
                old_price = round(price_int / 0.8)
                final_price = round(price_int * 1.12)
                price_per_month = round(final_price / 12)
                rec_new["old_price"] = str(old_price)
                rec_new["discount_percent"] = "20"
                rec_new["installment_months"] = "12"
                rec_new["price_per_month"] = str(price_per_month)
            except Exception as e:
                logger.info(f"⚠️ Ошибка при расчёте цены: {e}")

            hotels_parsed.append(rec_new)
            count_added_rows += 1
            logger.info(f"➕ Отель: {hotel_name_raw} | Дата: {date_std} | Цена: {price}")

            if limit and count_added_rows >= limit:
                logger.info(f"⛔ Достигнут лимит {limit}, останавливаем парсинг.")
                break

        except Exception as e:
            logger.warning(f"⚠️ Ошибка при обработке строки: {e}")
            continue

# ----------------------- МЕРДЖ С СУЩЕСТВУЮЩИМИ -----------------------

# Индекс свежепарсенных по ключу
parsed_index = {}
for rec in hotels_parsed:
    k = make_key(rec)
    if k not in parsed_index:
        parsed_index[k] = rec
    else:
        # объединяем даты, если один и тот же ключ встретился больше раза
        for dp in rec.get("dates_prices", []):
            d = normalize_date_to_standard(dp.get("date"))
            if not d:
                continue
            existing_dp = next((x for x in parsed_index[k]["dates_prices"] if normalize_date_to_standard(x["date"]) == d), None)
            if existing_dp:
                existing_dp["price"] = str(dp.get("price", existing_dp.get("price", "")))
            else:
                parsed_index[k]["dates_prices"].append({"date": d, "price": str(dp.get("price", ""))})

# Теперь сшиваем parsed_index в existing_index
for k, new_rec in parsed_index.items():
    if k in existing_index:
        base = existing_index[k]
        # dates_prices: обновляем по датам
        base.setdefault("dates_prices", [])
        ensure_dates_prices_standard(base)

        for dp in new_rec.get("dates_prices", []):
            d = normalize_date_to_standard(dp.get("date"))
            if not d:
                continue
            price = str(dp.get("price", ""))

            ex = next((x for x in base["dates_prices"] if normalize_date_to_standard(x.get("date")) == d), None)
            if ex:
                if str(ex.get("price", "")) != price:
                    ex["price"] = price  # обновляем цену на свежую
            else:
                base["dates_prices"].append({"date": d, "price": price})

        # можно обновить «витринные» поля (цены/скидки/рассрочку) из свежей записи
        for fld in ("price", "old_price", "discount_percent", "price_per_month", "installment_months", "seats"):
            if new_rec.get(fld):
                base[fld] = new_rec[fld]

        # пересчёт основного price как минимума
        recompute_primary_price(base)

    else:
        # Новый тур — просто добавляем
        existing_index[k] = new_rec
        # и тоже нормализуем даты на всякий случай
        ensure_dates_prices_standard(existing_index[k])
        recompute_primary_price(existing_index[k])
        logger.info(f"🆕 Добавлен новый тур: {new_rec.get('hotel','')}")

final_results = list(existing_index.values())

# ----------------------- ПРИСВОЕНИЕ ID -----------------------

existing_ids = set()
for item in final_results:
    if isinstance(item.get("id"), int):
        existing_ids.add(item["id"])

next_id = max(existing_ids, default=0) + 1
for hotel in final_results:
    if "id" not in hotel or not isinstance(hotel["id"], int):
        hotel["id"] = next_id
        next_id += 1

# ----------------------- СОХРАНЕНИЕ -----------------------

with open(filter_path, "w", encoding="utf-8") as f:
    json.dump(final_results, f, indent=2, ensure_ascii=False)

logger.info(f"✅ Сформировано {len(final_results)} туров (мердж по ключу country|city|hotel|meal|nights).")
print(f"Готово: {len(final_results)} туров сохранено в filter.json")
