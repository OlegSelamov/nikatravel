import subprocess
import datetime
import os
import time
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

CONFIG_PATH = "data/kazunion_config.json"

def read_config():
    with open(CONFIG_PATH, 'r', encoding="utf-8") as f:
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

def wait_for_loader(page):
    try:
        print("⏳ Ждём загрузку...")
        page.wait_for_selector("div.loader", state="attached", timeout=3000)
        page.wait_for_selector("div.loader", state="detached", timeout=15000)
        print("✅ Загрузка завершена")
    except:
        print("⚠️ Спиннер не обнаружен — продолжаем")

def run():
    config = read_config()
    nights = str(config.get("nights", [5])[0])
    adults = str(config.get("ADULT", 2))
    meals = config.get("meal", [])
    stars = config.get("STARS", [])
    currency = config.get("currency", "KZT")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("🔄 Открываем Kazunion...")
        page.goto("https://online.kazunion.com/search_tour", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        try:
            # Город
            page.evaluate("document.querySelector(\"select[name='TOWNFROMINC']\").style.display = 'block'")
            page.select_option("select[name='TOWNFROMINC']", config["city_code"])
            print(f"🏙 Город отправления выбран: {config['city_code']}")
            wait_for_loader(page)

            # Страна
            print("⏳ Ждём появление страны...")
            for _ in range(30):
                display = page.evaluate("getComputedStyle(document.querySelector(\"select[name='STATEINC']\")).display")
                if display != "none":
                    print("✅ Страна стала видимой")
                    break
                time.sleep(0.5)
            else:
                print("⚠️ Страна не появилась — пробуем разблокировать вручную")
                page.evaluate("document.querySelector(\"select[name='STATEINC']\").style.display = 'block'")
                page.evaluate("document.querySelector(\"select[name='STATEINC']\").style.opacity = '1'")
                time.sleep(1)

            # Проверяем, доступен ли код страны
            available_values = page.eval_on_selector_all(
                "select[name='STATEINC'] option",
                "opts => opts.map(opt => opt.value)"
            )

            if config["country_code"] not in available_values:
                print(f"❌ Страна с кодом {config['country_code']} недоступна для этого города!")
                return

            page.select_option("select[name='STATEINC']", config["country_code"])
            print(f"🌍 Страна выбрана: {config['country_code']}")
            wait_for_loader(page)

            # Дата
            page.click("input[name='CHECKIN_BEG']", force=True)
            page.fill("input[name='CHECKIN_BEG']", "")
            page.fill("input[name='CHECKIN_BEG']", config["departure_date"])
            page.keyboard.press("Enter")
            page.mouse.click(100, 100)  # клик, чтобы закрыть календарь
            page.wait_for_timeout(1000)
            print(f"📅 Установлена дата вылета: {config['departure_date']}")

            # Ночи — умное ожидание
            print("⏳ Ждём поле 'Ночей'...")

            # Максимум 20 попыток (10 сек)
            for _ in range(20):
                ready = page.evaluate("""
                    () => {
                        const el = document.querySelector("select[name='NIGHTS_FROM']");
                        if (!el) return false;
                        if (el.disabled || getComputedStyle(el).display === 'none') {
                            el.style.display = 'block';
                            el.disabled = false;
                        }
                        return !el.disabled && getComputedStyle(el).display !== 'none';
                    }
                """)
                if ready:
                    print("🌙 Поле 'Ночей' активировано")
                    break
                time.sleep(0.5)
            else:
                print("❌ Поле 'Ночей' так и не стало доступным — прерываем")
                return

            page.select_option("select[name='NIGHTS_FROM']", nights)
            print(f"🌙 Кол-во ночей установлено: {nights}")

            # Взрослые
            try:
                page.click(".ADULT_chosen .chosen-single", force=True)
                page.wait_for_timeout(500)
                options = page.locator(".ADULT_chosen .chosen-drop ul li")
                for i in range(options.count()):
                    if options.nth(i).inner_text().strip() == adults:
                        options.nth(i).click(force=True)
                        print(f"👥 Взрослых: {adults}")
                        break
            except Exception as e:
                print(f"❌ Ошибка при выборе взрослых: {e}")

            # Валюта
            try:
                page.evaluate("document.querySelector(\"select[name='CURRENCY']\").style.display = 'block'")
                page.select_option("select[name='CURRENCY']", currency)
                print(f"💱 Валюта: {currency}")
            except Exception as e:
                print(f"❌ Не удалось выбрать валюту: {e}")

            # Питание
            try:
                page.locator("input[name='MEALS_ANY']").click()
                page.wait_for_selector(".MEALS input[type='checkbox']", timeout=7000)
                for meal_code in meals:
                    checkbox = page.locator(f".MEALS input[type='checkbox'][value='{meal_code}']")
                    checkbox.wait_for(state="visible", timeout=3000)
                    if not checkbox.is_checked():
                        checkbox.check(force=True)
                        print(f"✅ Питание {meal_code} включено")
            except Exception as e:
                print(f"⚠️ Проблема с питанием: {e}")

            # Звезды
            try:
                page.wait_for_selector(".STARS", timeout=10000)
                for star in stars:
                    locator = page.locator(f".STARS input[type='checkbox'][value='{star}']")
                    if locator.is_visible() and not locator.is_checked():
                        locator.check(force=True)
                        print(f"⭐ Звезда {star} включена")
            except Exception as e:
                print(f"❌ Ошибка при установке звёзд: {e}")

            # Фильтры
            safe_check(page, "input[name='FREIGHT']")
            safe_check(page, "input[name='FILTER']")
            safe_check(page, "input[name='PARTITION_PRICE']")

            # Поиск
            try:
                page.wait_for_selector("button.load.right:not([disabled])", timeout=10000)
                page.click("button.load.right")
                page.wait_for_timeout(3000)
                page.click("button.load.right")
                print("🔍 Поиск запущен")
            except Exception as e:
                print(f"❌ Кнопка 'Искать' не сработала: {e}")

            # Сохраняем
            try:
                page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                page.wait_for_timeout(3000)
                html = page.content()
                Path("data").mkdir(exist_ok=True)
                with open("data/kazunion_result.html", "w", encoding="utf-8") as f:
                    f.write(html)
                page.screenshot(path="data/debug_table.png", full_page=True)
                print("📥 HTML и скриншот сохранены")

                os.system("python parserhtml.py")
                os.system("python auto_booking_scraper.py")
            except Exception as e:
                print(f"❌ Ошибка при сохранении или парсинге: {e}")

        finally:
            browser.close()

def auto_push():
    import subprocess, datetime, os

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subprocess.run(['git', 'config', '--global', 'user.name', 'RailwayBot'])
    subprocess.run(['git', 'config', '--global', 'user.email', 'railway@bot.com'])
    subprocess.run(['git', 'add', 'data/filter.json'])
    subprocess.run(['git', 'commit', '-m', f'Автообновление туров от {now}'])
    subprocess.run(['git', 'push', 'origin', 'main'])

if __name__ == "__main__":
    try:
        run()
        auto_push()
    except Exception as e:
        print(f"❌ Ошибка выполнения скрипта: {e}")



