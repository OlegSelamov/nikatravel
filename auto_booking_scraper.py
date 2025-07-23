import subprocess
import datetime
import os
import json
import shutil
from PIL import Image, ImageStat
import imagehash

from scraper_ddg import get_booking_url_by_hotel_name
from booking_scraper_vlite_plus import scrape_booking_vlite_plus, extract_description
import sys
import io
import logging

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("parser.log", encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
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
    logger.info("🚀 START: auto_booking_scraper запускается...")
    with open(FILTER_JSON, "r", encoding="utf-8") as f:
        tours = json.load(f)

    updated = 0

    for i, tour in enumerate(tours):
        if is_tour_filled(tour):
            logger.info(f"⏭ Уже заполнен: {tour['hotel']} — пропускаем")
            continue

        hotel_name = tour["hotel"]
        logger.info(f"🔍 [{i}] Ищем Booking для: {hotel_name}")
        url = get_booking_url_by_hotel_name(hotel_name)
        if not url:
            logger.info(f"❌ Booking не найден: {hotel_name}")
            continue

        logger.info(f"✅ Booking найден: {url}")

        folder_name = hotel_name.replace(" ", "_").replace("*", "").replace("/", "_")
        folder_path = f"data/{folder_name}"

        scrape_booking_vlite_plus(url, folder_path)
        if not os.path.isdir(folder_path):
            logger.info(f"❌ Папка не найдена: {folder_path}")
            continue

        image_files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]

        valid_images = [f for f in image_files if is_valid_image(f)]
        if not valid_images:
            logger.info(f"❌ Нет подходящих фото для {hotel_name}")
            continue

        unique_images = remove_similar_images(valid_images)
        unique_images.sort(key=lambda f: Image.open(f).size[0] * Image.open(f).size[1], reverse=True)

        gallery_filenames = []
        for idx, img_path in enumerate(unique_images):
            new_filename = f"{folder_name}_{idx+1}.jpg"
            dest_path = os.path.join(IMG_FOLDER, new_filename)
            if not os.path.exists(dest_path):
                shutil.copy(img_path, dest_path)
            gallery_filenames.append(new_filename)

        tour["gallery"] = gallery_filenames

        if gallery_filenames:
            scored = [(f, get_image_score(os.path.join(IMG_FOLDER, f))) for f in gallery_filenames]
            scored.sort(key=lambda x: x[1], reverse=True)
            tour["image"] = scored[0][0]

        extract_description(url, folder_path)
        desc_file = os.path.join(folder_path, "description.txt")
        if os.path.exists(desc_file):
            with open(desc_file, "r", encoding="utf-8") as f:
                tour["description"] = f.read().strip()
             
        tours[i] = tour
        updated += 1
        logger.info(f"✅ [{i}] Обновлено: {hotel_name}")

    # 💾 Сохраняем JSON один раз в конце
    with open(FILTER_JSON, "w", encoding="utf-8") as f:
        json.dump(tours, f, ensure_ascii=False, indent=2)
    logger.info("💾 filter.json сохранён после обработки всех туров")
# ✅ Автопуш после сохранения фильтра
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subprocess.run(['git', 'config', '--global', 'user.name', 'RailwayBot'])
    subprocess.run(['git', 'config', '--global', 'user.email', 'railway@bot.com'])
    subprocess.run(['git', 'add', '.'])
    subprocess.run(['git', 'commit', '-m', f'Автообновление туров после обработки Booking от {now}'])
    subprocess.run(['git', 'push', 'origin', 'main'])

    logger.info(f"📦 Всего обновлено туров: {updated}")
    missing = [t["hotel"] for t in tours if not is_tour_filled(t)]
    if missing:
        logger.info("🛑 Пропущены:")
        for name in missing:
            logger.info("  —", name)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.info(f"💥 ОШИБКА auto_booking_scraper: {e}")


