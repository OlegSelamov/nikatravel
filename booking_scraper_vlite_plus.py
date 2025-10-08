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

def safe_download(url, path, retries=3, timeout=15):
    """Скачивание с повторами и таймаутом"""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=timeout)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                return True
            else:
                logger.warning(f"⚠️ {url} вернул {r.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка скачивания {url} (попытка {attempt+1}): {e}")
        time.sleep(1)  # пауза между попытками
    return False

def scrape_booking_vlite_plus(url, folder_name="downloaded_images_plus", limit=180):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
    except Exception as e:
        logger.info(f"❌ Не удалось загрузить страницу: {e}")
        return
    if r.status_code != 200:
        logger.info(f"❌ Не удалось загрузить страницу: {r.status_code}")
        return

    urls = extract_hd_images_from_json(r.text)

    if not urls:
        logger.info("⚠️ HD-фотографии в JSON не найдены.")
        return

    # Ограничиваем количество фоток
    urls = urls[:limit]

    count = 0
    for i, src in enumerate(urls):
        filename = os.path.join(folder_name, f"photo_{i+1}.jpg")
        if safe_download(src, filename):
            logger.info(f"✅ Скачано: {filename}")
            count += 1

    logger.info(f"📦 Всего скачано: {count} изображений (лимит {limit})")

def extract_description(url, folder_path):
    import requests
    from bs4 import BeautifulSoup
    import os

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    def fetch_description(test_url, lang="ru"):
        try:
            resp = requests.get(test_url, headers=headers, timeout=20)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                selectors = [
                    "p[data-testid='property-description']",
                    "div#property_description_content",
                    "div[data-capla-component='property-description']",
                    "section[data-testid='property-description']",
                ]
                for sel in selectors:
                    block = soup.select_one(sel)
                    if block:
                        text = block.get_text(" ", strip=True)
                        if text and len(text) > 30:
                            logger.info(f"✅ Описание найдено ({lang}) селектором: {sel}")
                            return text
            else:
                logger.warning(f"⚠️ Booking вернул {resp.status_code} для {test_url}")
        except Exception as e:
            logger.warning(f"❌ Ошибка при запросе описания ({lang}): {e}")
        return None

    # 1. пробуем на русском
    if "?lang=" not in url:
        url_ru = url + ("&lang=ru" if "?" in url else "?lang=ru")
    else:
        url_ru = url
    description = fetch_description(url_ru, "ru")

    # 2. если нет — пробуем английский
    if not description:
        url_en = url.split("?")[0] + "?lang=en"
        description = fetch_description(url_en, "en")

    if not description:
        description = "Описание недоступно"

    # сохраняем в файл
    os.makedirs(folder_path, exist_ok=True)
    desc_file = os.path.join(folder_path, "description.txt")
    try:
        with open(desc_file, "w", encoding="utf-8") as f:
            f.write(description)
        logger.info(f"💾 Описание сохранено: {desc_file}")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка записи description.txt: {e}")

    return description

