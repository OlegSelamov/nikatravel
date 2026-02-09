
import os
import json
import shutil
import logging
from PIL import Image, ImageStat
import imagehash

#from scraper_ddg import get_booking_url_by_hotel_name
from booking_scraper_vlite_plus import scrape_booking_selenium

logger = logging.getLogger("parser_logger")
logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "parser.log")
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(file_handler)

HOTELS_JSON = "data/hotels.json"
IMG_FOLDER = "static/img"
os.makedirs(IMG_FOLDER, exist_ok=True)

def is_hotel_filled(hotel: dict) -> bool:
    return (
        isinstance(hotel.get("gallery"), list) and len(hotel["gallery"]) > 0 and
        isinstance(hotel.get("image"), str) and hotel["image"].strip() != "" and
        isinstance(hotel.get("description"), str) and hotel["description"].strip() != ""
    )

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

def main():
    logger.info("START: auto_booking_scraper запускается...")
    with open(HOTELS_JSON, "r", encoding="utf-8") as f:
        hotels = json.load(f)

    logger.info(f"🏨 Загружено {len(hotels)} отелей из hotels.json")

    updated = 0

    for i, (hotel_id, hotel) in enumerate(hotels.items()):
        if is_hotel_filled(hotel):
            logger.info(f"[{i}] Уже заполнен: {hotel['hotel']} — пропускаем")
            continue

        hotel_name = hotel["hotel"]
        logger.info(f"[{i}] Ищем Booking для: {hotel_name}")

        # URL теперь НЕ нужен — мы используем Google
        url = "google"

        logger.info(f"Booking найден: {url}")

        folder_path = os.path.join("data", "tmp", hotel_id)
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True)

        try:
            img_count, description = scrape_booking_selenium(url, folder_path)
            logger.info(f"Скачано {img_count} фото")
        except Exception as e:
            logger.error(f"Ошибка scrape_booking_selenium для {url}: {e}")
            continue

        image_files = []
        if os.path.isdir(folder_path):
            for f in os.listdir(folder_path):
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    image_files.append(os.path.join(folder_path, f))

        if not image_files:
            logger.info(f"Нет фото для {hotel_name}")
            continue

        valid_images = [f for f in image_files if is_valid_image(f)]
        if not valid_images:
            logger.info(f"Нет подходящих фото для {hotel_name}")
            continue

        unique_images = remove_similar_images(valid_images)
        unique_images.sort(key=lambda f: Image.open(f).size[0] * Image.open(f).size[1], reverse=True)

        gallery_filenames = []
        for idx, img_path in enumerate(unique_images):
            new_filename = f"{hotel_id}_{idx+1}.jpg"
            dest_path = os.path.join(IMG_FOLDER, new_filename)
            if not os.path.exists(dest_path):
                try:
                    shutil.copy(img_path, dest_path)
                except Exception as e:
                    logger.warning(f"Ошибка копирования {img_path} -> {dest_path}: {e}")
            gallery_filenames.append(new_filename)

        if gallery_filenames:
            scored = []
            for f in gallery_filenames:
                try:
                    score = get_image_score(os.path.join(IMG_FOLDER, f))
                except Exception:
                    score = 0
                scored.append((f, score))
            scored.sort(key=lambda x: x[1], reverse=True)

        # обновляем данные отеля в памяти
        hotel["gallery"] = gallery_filenames
        hotel["image"] = scored[0][0] if gallery_filenames else ""
        hotel["description"] = description.strip() if description else "Описание недоступно"

        hotels[hotel_id] = hotel
        updated += 1

        logger.info(f"[{i}] 🏨 Отель обновлён: {hotel['hotel']}")

        # сохраняем hotels.json
        try:
            with open(HOTELS_JSON, "w", encoding="utf-8") as f:
                json.dump(hotels, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ hotels.json сохранён после {hotel['hotel']}")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении hotels.json: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.info(f"ОШИБКА auto_booking_scraper: {e}")
