
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape_booking_vlite_plus(url, folder_path):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Не удалось получить страницу: {url}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    images = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and "bstatic" in src:
            images.append(src)

    os.makedirs(folder_path, exist_ok=True)
    for i, img_url in enumerate(images):
        try:
            img_data = requests.get(img_url).content
            with open(os.path.join(folder_path, f"{i}.jpg"), "wb") as f:
                f.write(img_data)
        except Exception as e:
            print(f"Ошибка скачивания {img_url}: {e}")

    print(f"✅ Скачано {len(images)} фото в {folder_path}")

def extract_description(url, folder_path):
    from selenium.webdriver.chrome.options import Options

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")

    chromedriver_path = os.path.join(os.path.dirname(__file__), "chromedriver.exe")
    service = Service(executable_path=chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    if "?lang=" not in url:
        if "?" in url:
            url += "&lang=ru"
        else:
            url += "?lang=ru"

    print(f"🌐 Открываем: {url}")
    driver.get(url)

    try:
        element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="property-description"]'))
        )
        description = element.text.strip()
        with open(os.path.join(folder_path, "description.txt"), "w", encoding="utf-8") as f:
            f.write(description)
        print("✅ Описание сохранено")
    except Exception as e:
        print(f"❌ Ошибка при извлечении описания: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    # Только для ручного теста
    url = input("Вставь ссылку на отель с Booking: ").strip()
    folder = input("Введи путь к папке отеля: ").strip()
    if url and folder:
        extract_description(url, folder)
