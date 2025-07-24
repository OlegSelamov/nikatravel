from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging, time, os, requests
from bs4 import BeautifulSoup

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "parser.log")

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(file_handler)

# Инициализация Selenium один раз
def init_driver():
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("start-maximized")
    options.add_argument("disable-infobars")
    options.add_argument("disable-popup-blocking")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

driver = init_driver()

def find_booking_link_duckduckgo(hotel_name):
    try:
        search_url = f"https://www.booking.com/searchresults.html?ss={hotel_name.replace(' ', '+')}"
        logger.info(f"🔍 Ищем на Booking: {search_url}")
        driver.get(search_url)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-testid='property-card']"))
        )

        cards = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='property-card']")
        if not cards:
            logger.warning("❌ Карточки отелей не найдены")
            return None

        first_card = cards[0]
        link_element = first_card.find_element(By.CSS_SELECTOR, "a")
        driver.execute_script("arguments[0].click();", link_element)

        original_tabs = driver.window_handles
        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > len(original_tabs))
        new_tab = driver.window_handles[-1]
        driver.switch_to.window(new_tab)
        WebDriverWait(driver, 10).until(lambda d: "/hotel/" in d.current_url)
        time.sleep(2)

        final_url = driver.current_url
        if "?lang=" not in final_url:
            final_url += "&lang=ru"

        logger.info(f"✅ Найден URL: {final_url}")
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        return final_url
    except Exception as e:
        logger.error(f"❌ Ошибка Selenium: {e}")
        return None

def get_booking_url_by_hotel_name(hotel_name):
    search_url = f"https://duckduckgo.com/html/?q=site:booking.com {hotel_name.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
    
    for attempt in range(3):
        try:
            time.sleep(2)
            response = requests.get(search_url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                result = soup.find("a", href=True)
                if result and "booking.com" in result["href"]:
                    logger.info(f"🔗 Найдена ссылка: {result['href']}")
                    return result["href"]
            else:
                logger.warning(f"⚠️ Ошибка DuckDuckGo: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Ошибка запроса DuckDuckGo: {e}")

    logger.info("⏳ Переключаемся на Selenium...")
    return find_booking_link_duckduckgo(hotel_name)

# Закрываем драйвер при завершении
import atexit
atexit.register(lambda: driver.quit())