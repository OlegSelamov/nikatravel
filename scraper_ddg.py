
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

def extract_real_booking_link(raw_link):
    # Добавляем схему, если отсутствует
    if raw_link.startswith("//"):
        raw_link = "https:" + raw_link
    try:
        query = urlparse(raw_link).query
        real_link = unquote(parse_qs(query).get("uddg", [raw_link])[0])
        return real_link
    except Exception:
        return raw_link

def get_booking_url_by_hotel_name(hotel_name):
    # Попробуем через DuckDuckGo
    try:
        query = f"site:booking.com {hotel_name}"
        ddg_url = f"https://duckduckgo.com/html/?q={query}"
        response = requests.get(ddg_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = [a["href"] for a in soup.find_all("a", href=True) if "booking.com" in a["href"]]
            if links:
                real_link = extract_real_booking_link(links[0])
                print(f"✅ Найдена ссылка через DuckDuckGo: {real_link}")
                return real_link
            else:
                print("⚠️ DuckDuckGo не вернул ссылок на Booking.")
        else:
            print(f"⚠️ Ошибка запроса DuckDuckGo: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Ошибка при поиске через DuckDuckGo: {e}")

    # Если не нашли - fallback через Selenium
    try:
        print("🔄 Пробуем искать напрямую на Booking через Selenium...")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        driver = webdriver.Chrome(options=options)
        driver.get("https://www.booking.com")

        search_box = driver.find_element(By.NAME, "ss")
        search_box.clear()
        search_box.send_keys(hotel_name)
        search_box.submit()
        time.sleep(3)

        # Ищем первый результат
        first_card = driver.find_element(By.CSS_SELECTOR, "div[data-testid='property-card']")
        link_element = first_card.find_element(By.CSS_SELECTOR, "a[data-testid='title-link']")
        booking_url = link_element.get_attribute("href")
        driver.quit()

        print(f"✅ Найдена ссылка через Booking: {booking_url}")
        return booking_url
    except Exception as e:
        print(f"❌ Не удалось найти ссылку на Booking: {e}")
        try:
            driver.quit()
        except:
            pass
        return None
