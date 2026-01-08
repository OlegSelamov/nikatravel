import os
import re
import time
import json
import logging
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------------------------------------------------------
# ЛОГИ
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "parser.log")

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
HEADERS = {"User-Agent": "Mozilla/5.0"}

COOKIES_FILE = "booking_cookies.json"

def google_find_booking_url(name):
    try:
        q = f'site:booking.com "{name}"'
        url = f"https://www.google.com/search?q={q.replace(' ', '+')}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "booking.com/hotel" in href:
                clean = href.split("url=")[-1].split("&")[0]
                return clean
    except:
        pass
    return None

# -------------------------------------------------------------
# Selenium Driver
# -------------------------------------------------------------
def create_driver():
    chrome_options = Options()

    # браузер с окном (НЕ headless)
    # если нужно headless — раскомментируй:
    # chrome_options.add_argument("--headless=new")

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--lang=ru-RU")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    )

    service = Service("C:/PRO/NIKATRAVEL/chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# -------------------------------------------------------------
# COOKIE: СОХРАНЕНИЕ
# -------------------------------------------------------------
def login_and_save_cookies():
    driver = create_driver()
    driver.get("https://account.booking.com/sign-in")

    print("\n🔥 ВОЙДИ В BOOKING В ОТКРЫВШЕМСЯ ОКНЕ.")
    print("После входа нажми ENTER в консоли.\n")
    input("➡ Нажми ENTER когда войдёшь в Booking: ")

    cookies = driver.get_cookies()
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)

    print("✔ Cookies сохранены: booking_cookies.json")
    driver.quit()

# -------------------------------------------------------------
# COOKIE: ЗАГРУЗКА
# -------------------------------------------------------------
def load_cookies(driver):
    if not os.path.exists(COOKIES_FILE):
        return False

    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        driver.get("https://www.booking.com")
        time.sleep(2)

        for c in cookies:
            c.pop("sameSite", None)
            c.pop("expiry", None)
            try:
                driver.add_cookie(c)
            except:
                pass

        driver.get("https://www.booking.com")
        time.sleep(2)
        return True

    except Exception as e:
        print("Ошибка загрузки cookies:", e)
        return False

# -------------------------------------------------------------
# Умная очистка названия отеля
# -------------------------------------------------------------
CITY_MAP = {
    "Баку": "Baku",
    "Габала": "Gabala",
    "Шеки": "Sheki",
    "Тбилиси": "Tbilisi",
    "Алматы": "Almaty",
    "Астана": "Astana",
}

def extract_city(name):
    for ru, en in CITY_MAP.items():
        if ru in name:
            return en
    return ""

def clean_hotel_name(name):
    for ru in CITY_MAP.keys():
        name = name.replace(f"({ru})", " ").replace(ru, " ")

    bad = ["5*", "4*", "3*", "2*", "1*", "*", "★", "⭐", "(", ")", ",", "  "]
    for b in bad:
        name = name.replace(b, " ")
    return " ".join(name.split()).strip()

def build_query(name):
    h = clean_hotel_name(name)
    city = extract_city(name)
    return f"{h} {city}" if city else h
    

# -------------------------------------------------------------
# УДАЛЕНИЕ МОДАЛОК Booking
# -------------------------------------------------------------
def kill_modals(driver):
    try:
        driver.execute_script("""
            document.querySelectorAll('[role="dialog"], .bui-modal, .modal-mask, [data-testid="overlay"]').forEach(e=>e.remove());
        """)
    except:
        pass
        
def normalize_title(text: str) -> str:
    """
    Приводим название к простому виду:
    - нижний регистр
    - убираем лишние символы
    - оставляем только буквы/цифры/пробелы
    """
    text = text.lower()
    # убираем звездочки, скобки и прочий мусор
    text = text.replace("5*", "").replace("4*", "").replace("3*", "")
    text = re.sub(r"[^a-zа-я0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def similarity_score(target: str, candidate: str) -> float:
    """
    Жёсткое сравнение: считаем, сколько слов из target
    реально присутствуют в candidate.
    Возвращаем коэффициент от 0 до 1.
    """
    t = normalize_title(target)
    c = normalize_title(candidate)

    t_words = [w for w in t.split() if len(w) > 2]
    c_words = [w for w in c.split() if len(w) > 2]

    if not t_words or not c_words:
        return 0.0

    common = sum(1 for w in t_words if w in c_words)
    return common / max(len(t_words), 1)

# -------------------------------------------------------------
# Поиск Booking URL через сайт Booking
# -------------------------------------------------------------
def find_booking_url(driver, hotel_name):
    # ---- Шаг 1: пробуем найти отель через Google ----
    google_url = google_find_booking_url(hotel_name)
    if google_url:
        logger.info(f"✔ Найден через Google: {google_url}")
        return google_url

    query = build_query(hotel_name)
    logger.info(f"🔎 Ищем на Booking: {query}")

    driver.get("https://www.booking.com")
    time.sleep(2)
    kill_modals(driver)

    try:
        search_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='ss']"))
        )
        search_input.click()
        search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.DELETE)
        time.sleep(0.3)

        search_input.send_keys(query)
        time.sleep(1.5)

        suggests = driver.find_elements(By.CSS_SELECTOR, "li[data-testid='autocomplete-result']")

        clicked = False
        clean_name = clean_hotel_name(hotel_name).lower()

        for s in suggests:
            txt = s.text.lower()
                
            # если подсказка — просто город → пропускаем
            city_only = txt.strip()
            if city_only in ["baku", "gabala", "sheki", "tbilisi", "almaty", "astana"]:
                continue
    
            # Берём первые 2 слова отеля для более точного совпадения
            clean_parts = clean_name.split()
            keywords = [w for w in clean_parts if len(w) > 3][:2]  # максимум 2 ключевых слова

            # Проверяем, что ОДНО из ключевых слов есть в подсказке
            if any(k in txt for k in keywords):
                # игнорируем мусорные подсказки (апартаменты, отели с похожими словами)
                bad_words = ["apartment", "apart", "hostel", "guest", "вакансии"]
                if any(b in txt for b in bad_words):
                    continue

                try:
                    s.click()
                    clicked = True
                    break
                except:
                    continue

        # Если клика НЕТ — жмём ENTER (Booking покажет отели сам)
        if not clicked:
            search_input.send_keys(Keys.ENTER)

        time.sleep(3)
        kill_modals(driver)

        # Ждём, пока страница результатов реально прогрузится
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "[data-testid='property-card']")
                )
            )
        except Exception:
            logger.warning("❌ Не дождались карточек отелей на странице")
            return None

        kill_modals(driver)
        
        # ---------------------------------------------------------------
        # Плавный скролл вниз, чтобы Booking показал кнопку "Показать ещё"
        # ---------------------------------------------------------------
        for _ in range(10):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(0.4)

        # ---------------------------------------------------------------
        # Автоматическая подгрузка всех карточек (клик по "Показать ещё")
        # ---------------------------------------------------------------
        while True:
            try:
                show_more = driver.find_element(By.CSS_SELECTOR, "button[data-testid='pagination-show-more-button']")
                driver.execute_script("arguments[0].scrollIntoView(true);", show_more)
                time.sleep(1)
                show_more.click()
                # после клика обязательно скроллим вниз,
                # иначе Booking НЕ загрузит следующую партию карточек
                for _ in range(5):
                    driver.execute_script("window.scrollBy(0, 1500);")
                    time.sleep(0.3)

                logger.info("⬇ Загружаем ещё результаты…")
                time.sleep(3)
            except:
                break  # кнопки больше нет

        # Ищем подходящий отель среди всех карточек
        cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='property-card']")
        
        # ----------------------------------------------------------------
        # Определяем целевой город из названия отеля (для защиты от подмены)
        # ----------------------------------------------------------------
        clean_lower = clean_name.lower()
        target_city = None

        city_keywords = {
            "phu quoc": ["phu quoc", "phuquoc", "fu kwok", "fuquoc"],
            "phuket": ["phuket", "puket", "пхукет"],
            "nha trang": ["nha trang", "nhatrang", "нячанг"],
            "bali": ["bali", "бал", "бали"],
            "dubai": ["dubai", "дубай"]
        }

        for city, variants in city_keywords.items():
            if any(v in clean_lower for v in variants):
                target_city = city
                break

        # Функция проверки города карточки
        def card_is_in_target_city(card, city):
            try:
                loc = card.find_element(By.CSS_SELECTOR, "[data-testid='location']").text.lower()
                return city in loc
            except:
                return True  # если Booking не показывает город — не выкидываем

        if not cards:
            logger.warning("❌ На странице нет карточек отелей")
            return None

        target_name = clean_hotel_name(hotel_name)
        best_score = 0.0
        best_href = None
        best_title = ""

        for card in cards:
            
            # Если определён целевой город — пропускаем карточки других городов
            if target_city and not card_is_in_target_city(card, target_city):
                continue
                
            try:
                title_el = card.find_element(By.CSS_SELECTOR, "[data-testid='title']")
                title_text = title_el.text.strip()
                href_el = card.find_element(By.CSS_SELECTOR, "a[data-testid='title-link']")
                href = href_el.get_attribute("href")
            except Exception:
                continue

            score = similarity_score(target_name, title_text)
            logger.info(f"🔍 Сравнение: '{hotel_name}' vs '{title_text}' → {score:.2f}")

            if score > best_score:
                best_score = score
                best_href = href
                best_title = title_text

        # Жёсткий порог совпадения — не меньше 0.7
        if best_href and best_score >= 0.7:
            logger.info(
                f"✔ Выбран отель по совпадению названия: '{best_title}' "
                f"(score={best_score:.2f}) → {best_href}"
            )
            return best_href
        else:
            logger.warning(
                f"❌ Не нашли подходящий отель для '{hotel_name}' "
                f"(best_score={best_score:.2f}, best_title='{best_title}')"
            )
            return None

    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return None

# -------------------------------------------------------------
# Извлечение JSON и фото
# -------------------------------------------------------------
def collect_json_data(driver, folder, limit=30):
    os.makedirs(folder, exist_ok=True)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    scripts = soup.find_all("script")

    images = set()
    descriptions = []

    def dig(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    dig(v)
                elif isinstance(v, str):
                    if "cf.bstatic.com" in v and "/xdata/images/hotel/" in v:
                        images.add(v)
                    if "desc" in k.lower() and len(v) > 100:
                        descriptions.append(v)
        elif isinstance(obj, list):
            for x in obj:
                dig(x)

    for script in scripts:
        txt = script.string or script.get_text(strip=True)
        if not txt or not (txt.startswith("{") or txt.startswith("[")):
            continue
        try:
            data = json.loads(txt)
            dig(data)
        except:
            pass

    images = list(images)

    # Сортировка: max2048 → max1600 → max1280 → max1024
    def score(url):
        return ("max2048" in url, "max1600" in url, "max1440" in url, "max1280" in url, "max1024" in url)

    images_sorted = sorted(images, key=score, reverse=True)[:limit]

    logger.info(f"Нашли фото: {len(images)} | Скачиваем: {len(images_sorted)}")

    downloaded = 0
    for idx, url in enumerate(images_sorted, 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                with open(os.path.join(folder, f"photo_{idx}.jpg"), "wb") as f:
                    f.write(r.content)
                downloaded += 1
        except:
            pass

    description = "Описание недоступно"
    if descriptions:
        descriptions.sort(key=len, reverse=True)
        description = descriptions[0]

    with open(os.path.join(folder, "description.txt"), "w", encoding="utf-8") as f:
        f.write(description)

    return downloaded, description

# -------------------------------------------------------------
# ГЛАВНАЯ ФУНКЦИЯ (использует твой auto_booking_scraper.py)
# -------------------------------------------------------------
# -------------------------------------------------------------
# GOOGLE через Selenium
# -------------------------------------------------------------
def google_selenium_find(driver, name):
    query = f'site:booking.com "{name}"'
    driver.get("https://www.google.com/search?q=" + query.replace(" ", "+"))
    time.sleep(2)
    kill_modals(driver)

    links = driver.find_elements(By.CSS_SELECTOR, "a")

    for link in links:
        href = link.get_attribute("href") or ""
        if "booking.com/hotel" in href:
            return href

    return None


# -------------------------------------------------------------
# ОСНОВНАЯ ФУНКЦИЯ SCRAPER
# -------------------------------------------------------------
def scrape_booking_selenium(url, folder, limit=30):
    hotel = os.path.basename(folder).replace("_", " ").strip()
    driver = create_driver()

    try:
        # ---- Загружаем cookies ----
        if load_cookies(driver):
            logger.info("✔ Cookies загружены.")
        else:
            logger.info("⚠ Cookies нет.")

        booking_url = None

        # ---- 1) Прямой URL ----
        if url and url not in ("None", "google"):
            booking_url = url

        # ---- 2) Google поиск ----
        elif url == "google":
            logger.info("🔎 Ищем через GOOGLE…")
            google_url = google_selenium_find(driver, hotel)
            if google_url:
                logger.info(f"🚀 Google нашёл: {google_url}")
                booking_url = google_url
            else:
                logger.info("⚠ Google не нашёл. Перехожу к Booking Search.")

        # ---- 3) Booking поиск ----
        if not booking_url:
            booking_url = find_booking_url(driver, hotel)

        if not booking_url:
            return 0, "Описание недоступно"

        # ---- 4) Открываем страницу ----
        driver.get(booking_url)
        time.sleep(4)
        kill_modals(driver)

        return collect_json_data(driver, folder, limit)

    finally:
        try:
            driver.quit()
        except:
            pass

# -------------------------------------------------------------
# Совместимость
# -------------------------------------------------------------
def scrape_booking_vlite_plus(url, folder_name="downloaded_images_plus", limit=30):
    return scrape_booking_selenium(url, folder_name, limit)

def extract_description(url, folder_path):
    downloaded, desc = scrape_booking_selenium(url, folder_path, limit=0)
    return desc

def safe_download(url, path):
    return False
