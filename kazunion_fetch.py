import shutil
import os
import time
import json
import datetime
import subprocess
import requests
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "parser.log")

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

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
            logger.info(f"✅ Чекбокс {selector} включен")
        else:
            logger.info(f"ℹ️ Чекбокс {selector} уже включён или скрыт")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось поставить галочку {selector}: {e}")

def wait_for_loader(page):
    try:
        logger.info("⏳ Ждём загрузку...")
        page.wait_for_selector("div.loader", state="attached", timeout=3000)
        page.wait_for_selector("div.loader", state="detached", timeout=15000)
        logger.info("✅ Загрузка завершена")
    except:
        logger.warning("⚠️ Спиннер не обнаружен — продолжаем")

def run():
    logger.info("🚀 kazunion_fetch.run() запущен")
    config = read_config()
    country = config.get("country_code", "ALL")
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    session_folder = Path(f"data/html_{country}_{timestamp}")
    session_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"📂 Папка для HTML сохранена: {session_folder}")
    nights = str(config.get("nights", [5])[0])
    adults = str(config.get("ADULT", 2))
    meals = config.get("meal", [])
    stars = config.get("STARS", [])
    currency = config.get("currency", "KZT")
    
    logger.info("📦 Конфиг загружен успешно")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        logger.info("🔄 Открываем Kazunion...")
        page.goto("https://online.kazunion.com/search_tour", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        try:
            # Город
            page.evaluate("document.querySelector(\"select[name='TOWNFROMINC']\").style.display = 'block'")
            page.select_option("select[name='TOWNFROMINC']", config["city_code"])
            logger.info(f"🏙 Город отправления выбран: {config['city_code']}")
            wait_for_loader(page)

            # Страна
            logger.info("⏳ Ждём появление страны...")
            for _ in range(30):
                display = page.evaluate("getComputedStyle(document.querySelector(\"select[name='STATEINC']\")).display")
                if display != "none":
                    logger.info("✅ Страна стала видимой")
                    break
                time.sleep(0.5)
            else:
                logger.warning("⚠️ Страна не появилась — пробуем разблокировать вручную")
                page.evaluate("document.querySelector(\"select[name='STATEINC']\").style.display = 'block'")
                page.evaluate("document.querySelector(\"select[name='STATEINC']\").style.opacity = '1'")
                time.sleep(1)

            # Проверяем, доступен ли код страны
            available_values = page.eval_on_selector_all(
                "select[name='STATEINC'] option",
                "opts => opts.map(opt => opt.value)"
            )

            if config["country_code"] not in available_values:
                logger.error(f"❌ Страна с кодом {config['country_code']} недоступна для этого города!")
                return

            page.select_option("select[name='STATEINC']", config["country_code"])
            logger.info(f"🌍 Страна выбрана: {config['country_code']}")
            wait_for_loader(page)           

            # Дата
            page.click("input[name='CHECKIN_BEG']", force=True)
            page.fill("input[name='CHECKIN_BEG']", "")
            page.fill("input[name='CHECKIN_BEG']", config["departure_date"])
            page.keyboard.press("Enter")
            page.mouse.click(100, 100)  # клик, чтобы закрыть календарь
            page.wait_for_timeout(1000)
            logger.info(f"📅 Установлена дата вылета: {config['departure_date']}")
            
            # Дата окончания
            page.click("input[name='CHECKIN_END']", force=True)
            page.fill("input[name='CHECKIN_END']", "")
            page.fill("input[name='CHECKIN_END']", config["departure_end"])
            page.keyboard.press("Enter")
            page.mouse.click(100, 100)
            page.wait_for_timeout(1000)
            logger.info(f"📅 Установлена дата окончания: {config['departure_end']}")

            # Ночи — умное ожидание
            logger.info("⏳ Ждём поле 'Ночей'...")

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
                    logger.info("🌙 Поле 'Ночей' активировано")
                    break
                time.sleep(0.5)
            else:
                logger.error("❌ Поле 'Ночей' так и не стало доступным — прерываем")
                return

            page.select_option("select[name='NIGHTS_FROM']", nights)
            logger.info(f"🌙 Кол-во ночей установлено: {nights}")

            # Взрослые
            try:
                page.click(".ADULT_chosen .chosen-single", force=True)
                page.wait_for_timeout(500)
                options = page.locator(".ADULT_chosen .chosen-drop ul li")
                for i in range(options.count()):
                    if options.nth(i).inner_text().strip() == adults:
                        options.nth(i).click(force=True)
                        logger.info(f"👥 Взрослых: {adults}")
                        break
            except Exception as e:
                logger.error(f"❌ Ошибка при выборе взрослых: {e}")

            # Валюта
            try:
                page.evaluate("document.querySelector(\"select[name='CURRENCY']\").style.display = 'block'")
                page.select_option("select[name='CURRENCY']", currency)
                logger.info(f"💱 Валюта: {currency}")
            except Exception as e:
                logger.error(f"❌ Не удалось выбрать валюту: {e}")

            # ===== Питание =====
            try:
                # Принудительно показываем блок
                page.evaluate("document.querySelector('.MEALS').style.display = 'block'")
                page.evaluate("document.querySelector('.MEALS').style.opacity = '1'")
                page.wait_for_selector(".MEALS input[type='checkbox']", state="visible", timeout=10000)

                # Сбрасываем все галочки
                all_meal_checkboxes = page.locator(".MEALS input[type='checkbox']")
                for i in range(all_meal_checkboxes.count()):
                    cb = all_meal_checkboxes.nth(i)
                    if cb.is_checked():
                        cb.uncheck(force=True)

                # Маппинг кодов питания
                meal_mapping = {
                    "AI": "10008",
                    "BB": "10002",
                    "FB": "10003",
                    "HB": "10004",
                    "RO": "10006",
                    "UAI": "10005"
                }

                # Ставим только нужные из config
                for meal_code in meals:  # meals берём из config
                    if meal_code in meal_mapping:
                        checkbox = page.locator(f".MEALS input[type='checkbox'][value='{meal_mapping[meal_code]}']")
                        if checkbox.count() > 0:
                            if not checkbox.first.is_checked():
                                checkbox.first.check(force=True)
                            logger.info(f"✅ Питание {meal_code} выбрано")
                        else:
                            logger.warning(f"⚠️ Чекбокс питания {meal_code} не найден!")
                    else:
                        logger.warning(f"⚠️ Неизвестный код питания: {meal_code}")

            except Exception as e:
                logger.warning(f"⚠️ Проблема с выбором питания: {e}")

            # Звезды
            try:
                page.wait_for_selector(".STARS", timeout=10000)
                for star in stars:
                    locator = page.locator(f".STARS input[type='checkbox'][value='{star}']")
                    if locator.is_visible() and not locator.is_checked():
                        locator.check(force=True)
                        logger.info(f"⭐ Звезда {star} включена")
            except Exception as e:
                logger.error(f"❌ Ошибка при установке звёзд: {e}")

            # Фильтры
            safe_check(page, "input[name='FREIGHT']")
            safe_check(page, "input[name='FILTER']")
            safe_check(page, "input[name='PARTITION_PRICE']")

            # Поиск
            try:
                logger.info("⏳ Ожидаем кнопку 'Искать'...")
                page.wait_for_selector("button.load.right:not([disabled])", timeout=15000)

                logger.info("▶ Первый клик по кнопке 'Искать'")
                page.click("button.load.right")
                page.wait_for_timeout(5000)  # ждём 5 секунд

                logger.info("▶ Второй клик по кнопке 'Искать'")
                page.click("button.load.right")
                page.wait_for_timeout(8000)  # ждём загрузки таблицы

                # Проверяем наличие таблицы
                if page.query_selector("table"):
                    logger.info("✅ Таблица с турами загружена")
                else:
                    logger.warning("⚠️ Таблица не появилась после двойного клика")

                logger.info("🔍 Поиск запущен (двойной клик)")
            except Exception as e:
                logger.error(f"❌ Кнопка 'Искать' не сработала: {e}")
                
            # Листаем страницы и сохраняем каждую
            page_num = 1
            Path("data/html").mkdir(parents=True, exist_ok=True)
            while True:
                # Сохраняем страницу
                html = page.content()
                file_path = session_folder / f"kazunion_page_{page_num}.html"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info(f"📥 Страница {page_num} сохранена: {file_path}")

                # Ищем следующую страницу
                next_page_selector = f".pager span.page[data-page='{page_num + 1}']"
                if page.query_selector(next_page_selector):
                    # Запоминаем текст первой строки таблицы
                    first_row_before = page.locator("table tbody tr").first.text_content()

                    # Кликаем
                    page.click(next_page_selector)
                    wait_for_loader(page)

                    # Ждём, пока изменится первая строка таблицы
                    try:
                        page.wait_for_function(
                            """(oldText) => {
                                const firstRow = document.querySelector("table tbody tr");
                                return firstRow && firstRow.textContent.trim() !== oldText.trim();
                            }""",
                            arg=first_row_before,
                            timeout=15000
                        )
                    except:
                        logger.warning("⚠️ Таблица не успела обновиться — сохраняем как есть")

                    page_num += 1
                else:
                    logger.info("🚩 Последняя страница достигнута.")
                    break
        
        except Exception as e:
            logger.error(f"❌ Ошибка при парсинге: {e}")
            
        finally:
            browser.close()            

        # Функция запуска команд
        def run_and_log(cmd):
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.stdout:
                logger.info(result.stdout)
            if result.stderr:
                logger.error(result.stderr)

        # Запускаем парсеры
        run_and_log("python parserhtml.py")
        run_and_log("python auto_booking_scraper.py")
