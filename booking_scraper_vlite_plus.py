import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import io
import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "parser.log")

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(file_handler)

def download_image(src, path):
    try:
        r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            with open(path, "wb") as f:
                f.write(r.content)
            return True
    except Exception as e:
        logger.info(f"Ошибка загрузки {src}: {e}")
    return False

def extract_hd_images_from_json(html):
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", type="application/json")

    urls = set()

    for script in scripts:
        try:
            data = json.loads(script.string)
            data_str = json.dumps(data)
            for match in data_str.split('"'):
                if "bstatic.com" in match and ("1024" in match or "max" in match) and ".jpg" in match:
                    urls.add(match)
        except Exception:
            continue

    return list(urls)

def normalize(text):
    return re.sub(r"[\s\*\-\(\)_]", "", text.lower())

def scrape_booking_vlite_plus(url, folder_name="downloaded_images_plus"):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        logger.info("❌ Не удалось загрузить страницу.")
        return

    urls = extract_hd_images_from_json(r.text)

    if not urls:
        logger.info("⚠️ HD-фотографии в JSON не найдены.")
        return

    count = 0
    for i, src in enumerate(urls):
        filename = os.path.join(folder_name, f"photo_{i+1}.jpg")
        if download_image(src, filename):
            logger.info(f"✅ Скачано: {filename}")
            count += 1

    logger.info(f"📦 Всего скачано: {count} изображений")

def extract_description(url, folder_path):
    try:
        chrome_options = Options()
        chrome_options.page_load_strategy = "eager"  # ускоряем загрузку
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1280,1024")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        chromedriver_path = os.path.join(os.path.dirname(__file__), "chromedriver.exe")
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)

        # Гарантируем русский язык
        if "?lang=" not in url:
            if "?" in url:
                url += "&lang=ru"
            else:
                url += "?lang=ru"

        logger.info(f"🌐 Итоговый URL: {url}")
        driver.get(url)

        os.makedirs(folder_path, exist_ok=True)
        description = "Описание недоступно"

        try:
            # Ждём именно <p data-testid="property-description">
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "p[data-testid='property-description']"))
            )
            element = driver.find_element(By.CSS_SELECTOR, "p[data-testid='property-description']")
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            tmp_text = element.text.strip()

            if tmp_text:
                description = tmp_text
                logger.info("✅ Описание найдено и загружено.")
            else:
                logger.warning("⚠ Описание пустое — сохраняем как 'Описание недоступно'.")

            # Сохраняем в файл description.txt
            with open(os.path.join(folder_path, "description.txt"), "w", encoding="utf-8") as f:
                f.write(description)
            logger.info(f"💾 Описание сохранено: {os.path.join(folder_path, 'description.txt')}")

            # Обновляем filter.json
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filter_path = os.path.join(script_dir, "data", "filter.json")

            data = []
            if os.path.exists(filter_path):
                try:
                    with open(filter_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    logger.info(f"⚠ Ошибка чтения filter.json: {e}")

            hotel_name = os.path.basename(folder_path)
            hotel_key = normalize(hotel_name)
            updated = False

            for entry in data:
                entry_name = normalize(entry.get("hotel", ""))
                if hotel_key in entry_name or entry_name in hotel_key:
                    entry["description"] = description
                    logger.info(f"✅ Обновлено описание для отеля: {entry['hotel']}")
                    updated = True
                    break

            if not updated:
                data.append({"hotel": hotel_name, "description": description})
                logger.info(f"➕ Добавлен новый отель: {hotel_name}")

            try:
                with open(filter_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info("📁 filter.json успешно обновлён.")
            except Exception as e:
                logger.info(f"⚠ Ошибка записи filter.json: {e}")

        except Exception as e:
            logger.warning(f"❌ Не удалось найти блок описания: {e}")
            # Даже если не нашли — создаём пустой файл
            with open(os.path.join(folder_path, "description.txt"), "w", encoding="utf-8") as f:
                f.write(description)

        driver.quit()

    except Exception as e:
        logger.info(f"⚠ Ошибка при вытаскивании описания: {e}")

    if __name__ == "__main__": 
        return