import os
import time
import json
import datetime
import subprocess
import requests
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright


logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("parser.log", encoding='utf-8')
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

    try:
        logger.info("📦 Тестовая заглушка. Создаём filter.json")
        test_data = {"test": "HELLO FROM RAILWAY"}
        with open("data/filter.json", "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)

        logger.info("📤 Вызываем send_to_render()")
        send_to_render()
        logger.info("✅ send_to_render() завершилась")

    except Exception as e:
        logger.error(f"💥 Ошибка в run(): {e}")


