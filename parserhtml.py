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
        
def clean_text_keep_case(x):
    if x is None:
        return ""
    s = str(x)
    s = s.replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def ensure_dates_prices_standard(rec: dict):
    dps = rec.get("dates_prices")
    if not isinstance(dps, list):
        rec["dates_prices"] = []
        return

    seen = {}
    for x in dps:
        d = normalize_date_to_standard(x.get("date"))
        if not d:
            continue
        price = str(x.get("price", "")).replace(" ", "")
        seen[d] = price

    rec["dates_prices"] = [
        {"date": d, "price": p} for d, p in sorted(seen.items())
    ]

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

offers_path = DATA_DIR / "offers.json"
hotels_path = DATA_DIR / "hotels.json"

def slugify(text: str) -> str:
    s = str(text).lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w]+", "_", s)
    return s.strip("_")

def safe_save_json(path: Path, data):
    import tempfile, os
    path = str(path)
    dir_name = os.path.dirname(path)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_name, encoding="utf-8") as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp_name = tmp.name
    os.replace(tmp_name, path)

# --- ЗАГРУЗКА offers.json ---
offers_list = []
if offers_path.exists():
    try:
        with open(offers_path, "r", encoding="utf-8") as f:
            offers_list = json.load(f)
        if not isinstance(offers_list, list):
            offers_list = []
    except Exception as e:
        logger.warning(f"⚠️ Ошибка чтения offers.json: {e}")
        offers_list = []

# Индекс offers по ключу: hotel_id|city|meal|nights
offers_index = {}
for off in offers_list:
    key = "|".join([
        normalize_str(off.get("hotel_id", "")),
        normalize_str(off.get("city", "")),
        normalize_str(off.get("meal", "")),
        normalize_str(off.get("nights", "")),
    ])
    offers_index[key] = off

# --- ЗАГРУЗКА hotels.json (опционально, чтобы помнить отели/страны) ---
hotels_map = {}
if hotels_path.exists():
    try:
        with open(hotels_path, "r", encoding="utf-8") as f:
            hotels_map = json.load(f)
        if not isinstance(hotels_map, dict):
            hotels_map = {}
    except Exception as e:
        logger.warning(f"⚠️ Ошибка чтения hotels.json: {e}")
        hotels_map = {}

# ----------------------- ПАРСИНГ HTML -----------------------

hotels_parsed = []  # будем складывать свежие записи перед мерджем
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

        date_raw = tds[1].get_text(strip=True)
        country_city_raw = tds[2].get_text(strip=True)
        nights_raw = tds[3].get_text(strip=True)

        # Если две цифры подряд, суммируем (наследуем твоё правило)
        if len(nights_raw) == 2 and nights_raw.isdigit():
            nights = str(int(nights_raw[0]) + int(nights_raw[1]))
        else:
            nights = nights_raw

        hotel_name_raw = clean_text_keep_case(tds[4].get_text())
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
            
        CITY_NORMALIZE = {
            "Астаны": "Астана",
            "из Астаны": "Астана",
            "Алматыдан": "Алматы",
            "Алматы": "Алматы",
        }

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
        city = CITY_NORMALIZE.get(city, city)

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
            "Анталия": "Турция",
            "Турция Стамбул": "Турция",
            "Турция Экскурсионные туры": "Турция",
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

        hotel_id = slugify(hotel_name_raw)

        # 1) hotels.json: записываем только если отеля ещё нет (НЕ затираем фото/описание)
        if hotel_id not in hotels_map:
            hotels_map[hotel_id] = {
                "hotel": hotel_name_raw,
                "country": country,
                "image": "",
                "gallery": [],
                "description": "",
            }

        # 2) offers.json: пишем динамику
        offer_new = {
            "hotel_id": hotel_id,
            "hotel": hotel_name_raw,   # можно оставить для удобства в админке/логах
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
            "dates_prices": [{"date": date_std, "price": price}],
        }

        # Расчёты цен (как у тебя было)
        try:
            price_int = int(price)
            old_price = round(price_int / 0.8)
            final_price = round(price_int * 1.12)
            price_per_month = round(final_price / 12)
            offer_new["old_price"] = str(old_price)
            offer_new["discount_percent"] = "20"
            offer_new["installment_months"] = "12"
            offer_new["price_per_month"] = str(price_per_month)
        except Exception as e:
            logger.info(f"⚠️ Ошибка при расчёте цены: {e}")

        hotels_parsed.append(offer_new)

            # Удаление временной папки с фотками после добавления тура
            #try:
                #import shutil
                #hotel_folder = DATA_DIR / "".join(c for c in hotel_name_raw if c.isalnum() or c in " _-")
               # if hotel_folder.exists():
                    #shutil.rmtree(hotel_folder)
                    #logger.info(f"🧹 Удалена папка с фото: {hotel_folder}")
            #except Exception as e:
                #logger.warning(f"⚠️ Ошибка при удалении временной папки с фото: {e}")

        #except Exception as e:
            #logger.warning(f"⚠️ Ошибка при обработке строки: {e}")
            #continue

# ----------------------- МЕРДЖ С СУЩЕСТВУЮЩИМИ -----------------------

# --- МЕРДЖ: свежие offers (hotels_parsed) -> offers_index ---
parsed_index = {}

for off in hotels_parsed:
    k = "|".join([
        normalize_str(off.get("hotel_id", "")),
        normalize_str(off.get("city", "")),
        normalize_str(off.get("meal", "")),
        normalize_str(off.get("nights", "")),
    ])
    if k not in parsed_index:
        parsed_index[k] = off
    else:
        # объединяем даты внутри одного запуска
        for dp in off.get("dates_prices", []):
            d = normalize_date_to_standard(dp.get("date"))
            if not d:
                continue
            ex = next((x for x in parsed_index[k]["dates_prices"] if normalize_date_to_standard(x.get("date")) == d), None)
            if ex:
                ex["price"] = str(dp.get("price", ex.get("price", "")))
            else:
                parsed_index[k]["dates_prices"].append({"date": d, "price": str(dp.get("price", ""))})

# мердж в общий offers_index (старые + новые)
for k, new_off in parsed_index.items():
    if k in offers_index:
        base = offers_index[k]
        base.setdefault("dates_prices", [])
        ensure_dates_prices_standard(base)

        # даты: обновить/добавить
        for dp in new_off.get("dates_prices", []):
            d = normalize_date_to_standard(dp.get("date"))
            if not d:
                continue
            price = str(dp.get("price", ""))
            ex = next((x for x in base["dates_prices"] if normalize_date_to_standard(x.get("date")) == d), None)
            if ex:
                ex["price"] = price
            else:
                base["dates_prices"].append({"date": d, "price": price})

        # обновляем витринные поля
        for fld in ("price", "old_price", "discount_percent", "price_per_month", "installment_months", "seats"):
            if new_off.get(fld):
                base[fld] = new_off[fld]

        recompute_primary_price(base)
    else:
        offers_index[k] = new_off
        ensure_dates_prices_standard(offers_index[k])
        recompute_primary_price(offers_index[k])

offers_final = list(offers_index.values())

# --- СОХРАНЕНИЕ offers.json + hotels.json ---
safe_save_json(offers_path, offers_final)
safe_save_json(hotels_path, hotels_map)

logger.info(f"✅ Сформировано {len(offers_final)} offers (ключ hotel_id|city|meal|nights).")
print(f"Готово: {len(offers_final)} offers сохранено в offers.json, hotels: {len(hotels_map)}")