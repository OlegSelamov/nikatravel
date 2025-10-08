# auto_booking_scraper.py
import subprocess
import datetime
import os
import json
import shutil
from PIL import Image, ImageStat
import imagehash
import re
import requests
import sys
import io
import logging

# импорт Booking-утилит
from booking_scraper_vlite_plus import normalize, scrape_booking_vlite_plus, extract_description
from scraper_ddg import get_booking_url_by_hotel_name

# Настройка UTF-8 для stdout (Windows)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "parser.log")

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(file_handler)

FILTER_JSON = "data/filter.json"
IMG_FOLDER = "static/img"
os.makedirs(IMG_FOLDER, exist_ok=True)

def is_valid_image(file_path):
    try:
        with Image.open(file_path) as img:
            width, _ = img.size
            return width >= 500
    except Exception:
        return False

def are_images_similar(img1, img2, threshold=5):
    hash1 = imagehash.phash(Image.open(img1))
    hash2 = imagehash.phash(Image.open(img2))
    return hash1 - hash2 <= threshold

def remove_similar_images(image_paths):
    unique = []
    for img_path in image_paths:
        is_duplicate = False
        for u in unique:
            if are_images_similar(img_path, u):
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(img_path)
    return unique

def get_image_score(image_path):
    try:
        img = Image.open(image_path).convert('RGB')
        stat = ImageStat.Stat(img)
        brightness = sum(stat.mean) / 3
        contrast = sum(stat.stddev) / 3

        r, g, b = stat.mean
        blue_ratio = b / max(r + g + 1, 1)

        score = brightness + contrast
        if blue_ratio > 0.6:
            score *= 1.5

        return score
    except Exception:
        return 0

def is_tour_filled(tour):
    return (
        isinstance(tour.get("gallery"), list) and len(tour["gallery"]) > 0 and
        isinstance(tour.get("image"), str) and tour["image"].strip() != "" and
        isinstance(tour.get("description"), str) and tour["description"].strip() != ""
    )

def main():
    logger.info("START: auto_booking_scraper запускается...")
    with open(FILTER_JSON, "r", encoding="utf-8") as f:
        tours = json.load(f)
        
    logger.info(f"🔢 Загружено {len(tours)} туров из filter.json")

    updated = 0   
    
    for i, tour in enumerate(tours):
        if is_tour_filled(tour):
            logger.info(f"[{i}] Уже заполнен: {tour['hotel']} — пропускаем")
            continue

        hotel_name = tour["hotel"]
        logger.info(f"[{i}] Ищем Booking для: {hotel_name}")

        # ---------- ВОССТАНАВЛИВАЕМ Booking-цепочку ----------
        url = get_booking_url_by_hotel_name(hotel_name, tour.get("country", ""))
        if url:
            tour["hotel_url"] = url
        else:
            logger.info(f"Booking не найден: {hotel_name}")
            # возможно, хотим пробовать позже — пропускаем
            continue

        logger.info(f"Booking найден: {url}")

        folder_name = hotel_name.replace(" ", "_").replace("*", "").replace("/", "_")
        folder_path = f"data/{folder_name}"

        # удаляем старую папку (опционально) — чтобы не мешали старые миниатюры
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
            except Exception:
                pass

        # Запускаем парсер Booking (он создаст папку folder_path с фото и description.txt)
        try:
            # если у тебя scrape_booking_vlite_plus принимает (url, folder_path) — подставь так.
            # В моём варианте предполагаю, что функция умеет принять URL и папку.
            scrape_booking_vlite_plus(url, folder_path)
        except Exception as e:
            logger.error(f"Ошибка запуска scrape_booking_vlite_plus для {url}: {e}")
            # пробуем fallback: extract_description и продолжаем (возможно фото не скачались)
            try:
                extract_description(url, folder_path)
            except Exception as e2:
                logger.error(f"Ошибка extract_description fallback: {e2}")

        # собираем локальные файлы из папки
        image_files = []
        if os.path.isdir(folder_path):
            for f in os.listdir(folder_path):
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    image_files.append(os.path.join(folder_path, f))

        if not image_files:
            logger.info(f"Нет фото для {hotel_name}")
            continue

        # фильтруем по разрешению
        valid_images = [f for f in image_files if is_valid_image(f)]
        if not valid_images:
            logger.info(f"Нет подходящих фото для {hotel_name}")
            continue

        # удаляем похожие и сортируем
        unique_images = remove_similar_images(valid_images)
        unique_images.sort(key=lambda f: Image.open(f).size[0] * Image.open(f).size[1], reverse=True)

        gallery_filenames = []
        for idx, img_path in enumerate(unique_images):
            new_filename = f"{folder_name}_{idx+1}.jpg"
            dest_path = os.path.join(IMG_FOLDER, new_filename)
            if not os.path.exists(dest_path):
                try:
                    shutil.copy(img_path, dest_path)
                except Exception as e:
                    logger.warning(f"Ошибка копирования {img_path} -> {dest_path}: {e}")
            gallery_filenames.append(new_filename)

        tour["gallery"] = gallery_filenames

        if gallery_filenames:
            scored = []
            for f in gallery_filenames:
                try:
                    score = get_image_score(os.path.join(IMG_FOLDER, f))
                except Exception:
                    score = 0
                scored.append((f, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            tour["image"] = scored[0][0]

        # Описание: если парсер Booking положил description.txt — читаем
        desc_file = os.path.join(folder_path, "description.txt")
        if os.path.exists(desc_file):
            try:
                with open(desc_file, "r", encoding="utf-8") as fd:
                    tour["description"] = fd.read().strip()
            except Exception:
                pass
        else:
            # fallback: попробуем extract_description если ещё не делали
            try:
                extract_description(url, folder_path)
                if os.path.exists(desc_file):
                    with open(desc_file, "r", encoding="utf-8") as fd:
                        tour["description"] = fd.read().strip()
            except Exception:
                pass

        tours[i] = tour
        updated += 1
        logger.info(f"[{i}] Обновлено: {hotel_name}")

        # Сохраняем JSON сразу после каждого тура
        try:
            with open(FILTER_JSON, "w", encoding="utf-8") as f:
                json.dump(tours, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ JSON обновлён после {hotel_name}")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении filter.json после {hotel_name}: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.info(f"ОШИБКА auto_booking_scraper: {e}")
