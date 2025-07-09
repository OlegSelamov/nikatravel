from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
import sys
import io

def find_booking_link_duckduckgo(hotel_name):
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("start-maximized")
    options.add_argument("disable-infobars")
    options.add_argument("disable-popup-blocking")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        search_url = f"https://www.booking.com/searchresults.html?ss={hotel_name.replace(' ', '+')}"
        logger.info(f"🔍 Открываем Booking: {search_url}")
        driver.get(search_url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='property-card']"))
        )

        cards = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='property-card']")
        if not cards:
            raise Exception("❌ Карточки отелей не найдены")

        first_card = cards[0]
        link_element = first_card.find_element(By.CSS_SELECTOR, "a")
        logger.info("👆 Кликаем по карточке...")

        original_tabs = driver.window_handles
        driver.execute_script("arguments[0].click();", link_element)

        # ⏳ Ждём открытия новой вкладки
        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > len(original_tabs))
        new_tabs = driver.window_handles
        new_tab = [tab for tab in new_tabs if tab not in original_tabs][0]
        driver.switch_to.window(new_tab)

        WebDriverWait(driver, 10).until(lambda d: "/hotel/" in d.current_url)
        time.sleep(2)

        final_url = driver.current_url

        # Гарантируем русский язык:
        if "?lang=" not in final_url:
            if "?" in final_url:
                final_url += "&lang=ru"
            else:
                final_url += "?lang=ru"

        logger.info(f"✅ Финальный URL: {final_url}")
        return final_url

    except Exception as e:
        logger.info(f"❌ Ошибка при переходе: {e}")
        with open("booking_debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        return None
   
from duckduckgo_search import DDGS
import logging

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("parser.log", encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(file_handler)

def get_booking_url_by_hotel_name(hotel_name):
    try:
        query = f"{hotel_name} site:booking.com"
        search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        time.sleep(5)

        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = soup.find_all("a", href=True)
            for link in links:
                href = link["href"]
                if "booking.com" in href:
                    # Если ссылка обёрнута DuckDuckGo, вытаскиваем настоящий адрес
                    if "uddg=" in href:
                        url = href.split("uddg=")[-1]
                        return unquote(url).split("&")[0]
                    return href
        else:
            logger.info(f"⚠️ Ошибка запроса DuckDuckGo: {response.status_code}")
    except Exception as e:
        logger.info(f"❌ Ошибка при поиске отеля: {e}")

    return None