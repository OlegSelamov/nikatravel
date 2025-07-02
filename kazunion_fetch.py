import time
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

CONFIG_PATH = "data/kazunion_config.json"

def read_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def safe_check(page, selector):
    try:
        checkbox = page.locator(selector)
        checkbox.wait_for(timeout=5000)
        if checkbox.is_visible() and not checkbox.is_checked():
            checkbox.check(force=True)
            print(f"✅ Чекбокс {selector} включен")
        else:
            print(f"ℹ️ Чекбокс {selector} уже включён или скрыт")
    except Exception as e:
        print(f"⚠️ Не удалось поставить галочку {selector}: {e}")

def run():
    config = read_config()
    nights = str(config.get("nights", [5])[0])
    adults = str(config.get("ADULT", 2))
    meals = config.get("meal", [])
    stars = config.get("STARS", [])
    currency = config.get("currency", "KZT")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        print("🔄 Открываем Kazunion...")
        page.goto("https://online.kazunion.com/search_tour")
        page.wait_for_timeout(10000)

        try:
            page.evaluate("document.querySelector(\"select[name='TOWNFROMINC']\").style.display = 'block'")
            page.evaluate("document.querySelector(\"select[name='TOWNFROMINC']\").style.opacity = '1'")
            page.select_option("select[name='TOWNFROMINC']", config["city_code"])
            page.wait_for_timeout(1000)

            page.evaluate("document.querySelector(\"select[name='STATEINC']\").style.display = 'block'")
            page.evaluate("document.querySelector(\"select[name='STATEINC']\").style.opacity = '1'")
            page.select_option("select[name='STATEINC']", config["country_code"])
            page.wait_for_timeout(2000)

            # Дата
            page.click("input[name='CHECKIN_BEG']")
            page.wait_for_timeout(500)
            page.fill("input[name='CHECKIN_BEG']", "")
            page.fill("input[name='CHECKIN_BEG']", config["departure_date"])
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(1000)

            # Ночи
            try:
                page.evaluate("document.querySelector(\"select[name='NIGHTS_FROM']\").style.display = 'block'")
                page.evaluate("document.querySelector(\"select[name='NIGHTS_FROM']\").style.opacity = '1'")
                page.wait_for_timeout(500)
                page.select_option("select[name='NIGHTS_FROM']", nights)
                print(f"✅ Ночи установлены: {nights}")
            except Exception as e:
                print(f"❌ Ошибка при выборе ночей: {e}")

            # Взрослые
            try:
                page.click(".ADULT_chosen .chosen-single", force=True)
                page.wait_for_timeout(500)
                options = page.locator(".ADULT_chosen .chosen-drop ul li")
                count = options.count()
                found = False
                for i in range(count):
                    text = options.nth(i).inner_text().strip()
                    if text == adults:
                        options.nth(i).click(force=True)
                        print(f"✅ Взрослые: {text}")
                        found = True
                        break
                if not found:
                    print(f"⚠️ Вариант '{adults}' не найден среди взрослых")
            except Exception as e:
                print(f"❌ Ошибка при выборе взрослых: {e}")

            # Валюта
            print("💱 Устанавливаем валюту...")
            page.evaluate("document.querySelector(\"select[name='CURRENCY']\").style.display = 'block'")
            page.evaluate("document.querySelector(\"select[name='CURRENCY']\").style.opacity = '1'")
            page.select_option("select[name='CURRENCY']", currency)
            print("💱 Валюта выбрана")

            # Питание
            try:
                page.locator("input[name='MEALS_ANY']").click()
                page.wait_for_selector(".MEALS input[type='checkbox']", timeout=5000)
                for meal_code in meals:
                    try:
                        checkbox = page.locator(f".MEALS input[type='checkbox'][value='{meal_code}']")
                        checkbox.wait_for(timeout=3000)
                        if checkbox.is_visible() and not checkbox.is_checked():
                            checkbox.check(force=True)
                            print(f"✅ Питание {meal_code} включено")
                        else:
                            print(f"ℹ️ Питание {meal_code} уже выбрано или не видно")
                    except Exception as inner_e:
                        print(f"⚠️ Питание {meal_code} не найдено или скрыто: {inner_e}")
            except Exception as e:
                print(f"⚠️ Не удалось открыть блок питания: {e}")

            # Звезды
            print("⏳ Ждём блок звёзд...")
            page.wait_for_selector(".STARS", timeout=10000)
            print("✅ Отмечаем звёзды...")
            for star_val in stars:
                try:
                    locator = page.locator(f".STARS input[type='checkbox'][value='{star_val}']")
                    locator.wait_for(timeout=5000)
                    if not locator.is_checked():
                        locator.check(force=True)
                        print(f"⭐ Звезда {star_val} включена")
                except Exception as e:
                    print(f"⚠️ Не удалось включить звезду {star_val}: {e}")

            # Стандартные фильтры
            print("✅ Включаем стандартные фильтры...")
            safe_check(page, "input[name='FREIGHT']")
            safe_check(page, "input[name='FILTER']")
            safe_check(page, "input[name='PARTITION_PRICE']")

            print("▶️ Ждём кнопку 'Искать' и кликаем дважды...")
            page.wait_for_selector("button.load.right:not([disabled])", timeout=10000)
            page.click("button.load.right")
            page.wait_for_timeout(5000)
            page.click("button.load.right")

            try:
                # Прокручиваем вниз снова — чтобы ленивая таблица точно загрузилась
                page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                page.wait_for_timeout(3000)

                # Сохраняем HTML
                html = page.content()
                Path("data").mkdir(exist_ok=True)
                with open("data/kazunion_result.html", "w", encoding="utf-8") as f:
                    f.write(html)

                page.screenshot(path="data/debug_table.png", full_page=True)
                print("✅ HTML сохранён как kazunion_result.html")
                print("✅ Скриншот страницы: debug_table.png")

                os.system("python parserhtml.py")
                os.system("python auto_booking_scraper.py")

            except Exception as e:
                print(f"❌ Таблица не найдена или не сохранена: {e}")

        finally:
            browser.close()

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
