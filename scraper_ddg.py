import re
import os
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === ЛОГИРОВАНИЕ ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "parser.log")

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(file_handler)

def clean_hotel_name(hotel_name):
    hotel_name = re.sub(r"\([^)]*\)", "", hotel_name)  # убираем скобки
    hotel_name = re.sub(r"\d\*\s*", "", hotel_name)    # убираем звездность
    hotel_name = re.sub(r"[,\s]+", " ", hotel_name)    # убираем лишние пробелы/запятые
    return hotel_name.strip()

def get_booking_url_by_hotel_name(hotel_name):
    cleaned_name = clean_hotel_name(hotel_name)
    logger.info(f"🔎 Ищу напрямую на Booking: {cleaned_name}")

    options = Options()
    # Видимый режим (можно вернуть headless при переносе на сервер)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,1024")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(25)

    try:
        driver.get("https://www.booking.com")

        # Ждём поле поиска
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "ss"))
        )

        # Вводим название
        search_box = driver.find_element(By.NAME, "ss")
        search_box.clear()
        search_box.send_keys(cleaned_name)

        # Ждём и кликаем первую подсказку
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li[data-i='0']"))
            )
            driver.find_element(By.CSS_SELECTOR, "li[data-i='0']").click()
            logger.info("✅ Кликнул первую подсказку")
        except:
            logger.warning("⚠️ Подсказка не найдена, выполняю поиск напрямую")
            search_box.submit()

        # Ждём карточки
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-testid='property-card']"))
        )

        # Берём ссылку из первой карточки
        first_card = driver.find_element(By.CSS_SELECTOR, "div[data-testid='property-card']")
        photo_url = first_card.find_element(By.CSS_SELECTOR, "a[data-testid='title-link']").get_attribute("href")
        clean_url = photo_url.split("?")[0]
        logger.info(f"📌 Чистый URL для описания: {clean_url}")

        # Переходим на страницу отеля
        driver.get(clean_url)
        try:
            # Пробуем найти старый блок описания
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "property_description_content"))
            )
            description = driver.find_element(By.ID, "property_description_content").text.strip()
            logger.info(f"✅ Описание найдено (старый блок), длина: {len(description)} символов")
        except:
            # Пробуем новый формат
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-capla-component-boundary*='PropertyDescription']"))
                )
                description = driver.find_element(By.CSS_SELECTOR, "div[data-capla-component-boundary*='PropertyDescription']").text.strip()
                logger.info(f"✅ Описание найдено (новый блок), длина: {len(description)} символов")
            except:
                logger.warning("❌ Описание не найдено")
                description = ""

        # Здесь можно сохранить описание, если у тебя есть логика записи
        # например: save_description_to_json(hotel_name, description)

        # Возвращаем ссылку для фото (как раньше)
        return photo_url

    except Exception as e:
        logger.error(f"❌ Ошибка поиска на Booking: {e}")
        return None

    finally:
        driver.quit()
