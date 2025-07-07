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

def download_image(src, path):
    try:
        r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            with open(path, "wb") as f:
                f.write(r.content)
            return True
    except Exception as e:
        print(f"Ошибка загрузки {src}: {e}")
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
        print("❌ Не удалось загрузить страницу.")
        return

    urls = extract_hd_images_from_json(r.text)

    if not urls:
        print("⚠️ HD-фотографии в JSON не найдены.")
        return

    count = 0
    for i, src in enumerate(urls):
        filename = os.path.join(folder_name, f"photo_{i+1}.jpg")
        if download_image(src, filename):
            print(f"✅ Скачано: {filename}")
            count += 1

    print(f"📦 Всего скачано: {count} изображений")

def extract_description(url, folder_path):
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1280,1024")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        chromedriver_path = os.path.join(os.path.dirname(__file__), "chromedriver.exe")
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(60)
        if "?lang=" not in url:
            if "?" in url:
                url += "&lang=ru"
            else:
                url += "?lang=ru"

        print("🌐 Итоговый URL:", url)
        driver.get(url)
        
        os.makedirs(folder_path, exist_ok=True)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="property-description"]'))
            )
            element = driver.find_element(By.CSS_SELECTOR, '[data-testid="property-description"]')
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            description = element.text.strip()

            if not description:
                print("⚠️ Описание пустое — не сохраняем в JSON.")
            else:
                with open(os.path.join(folder_path, "description.txt"), "w", encoding="utf-8") as f:
                    f.write(description)

                print("📄 Описание успешно сохранено через Selenium (element.text)")
                print("📌 Вставляемое описание:", description[:100], "...")

            # Добавляем в filter.json
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filter_path = os.path.join(script_dir, "data", "filter.json")

            if os.path.exists(filter_path):
                with open(filter_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                hotel_name = os.path.basename(folder_path)
                hotel_key = normalize(hotel_name)
                updated = False

                for entry in data:
                    entry_name = normalize(entry.get("hotel", ""))
                    print("📌 hotel_key:", hotel_key)
                    print("🔍 Сравниваем с:", entry_name)
                    print("🔍 Проверяем:", entry.get("hotel", "NO HOTEL"))

                    if hotel_key in entry_name or entry_name in hotel_key:
                        print("💾 Записываем в JSON:", description[:100], "...")
                        entry["description"] = description
                        print("📋 Старая строка JSON:", entry)
                        print("✅ Найден отель и обновлён:", entry["hotel"])
                        updated = True
                        break

                if updated:
                    with open(filter_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                        f.close()
                        print("📁 Записали filter.json — открой и проверь вручную.")
                        print("✅ Описание обновлено в filter.json")
                else:
                    print(f"⚠️ Отель не найден в filter.json. Проверь имя папки и отеля.")
            else:
                print("⚠️ Файл filter.json не найден по пути data/filter.json")


        except:
            print("❌ Блок data-testid='property-description' не найден даже после ожидания")

        driver.quit()

    except Exception as e:
        print(f"⚠️ Ошибка при вытаскивании описания: {e}")

    if __name__ == "__main__": 
        return
