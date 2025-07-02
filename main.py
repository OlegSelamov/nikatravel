import json
import os
import re
import hashlib
from PIL import Image
import imagehash
from auto_booking_scraper import get_booking_url_by_hotel_name, scrape_booking_photos

def sanitize_folder_name(name):
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'\d\*', '', name)
    return name.strip().replace(" ", "_")

def gallery_exists(hotel_name):
    folder = sanitize_folder_name(hotel_name)
    gallery = os.path.join("data", folder, "gallery")
    if not os.path.exists(gallery):
        return False
    files = [f for f in os.listdir(gallery) if f.lower().endswith((".jpg", ".jpeg"))]
    return len(files) >= 3

def get_visual_hash(image_path):
    try:
        with Image.open(image_path) as img:
            return imagehash.average_hash(img)
    except:
        return None

def filter_and_deduplicate(folder_path, min_width=500, hash_threshold=5):
    import shutil
    output_folder = os.path.join(folder_path, "filtered")

    if os.path.exists(output_folder):
        for f in os.listdir(output_folder):
            os.remove(os.path.join(output_folder, f))
    else:
        os.makedirs(output_folder, exist_ok=True)

    seen_hashes = []
    kept = 0

    for file in os.listdir(folder_path):
        path = os.path.join(folder_path, file)
        if os.path.isfile(path) and file.lower().endswith((".jpg", ".jpeg", ".png")):
            try:
                with Image.open(path) as img:
                    if img.width >= min_width:
                        img_hash = imagehash.average_hash(img)
                        if any(abs(img_hash - h) < hash_threshold for h in seen_hashes):
                            continue
                        seen_hashes.append(img_hash)
                        img.save(os.path.join(output_folder, file))
                        kept += 1
            except:
                continue

    for file in os.listdir(folder_path):
        path = os.path.join(folder_path, file)
        if os.path.isfile(path) and file.lower().endswith((".jpg", ".jpeg", ".png")):
            os.remove(path)

    for file in os.listdir(output_folder):
        shutil.move(os.path.join(output_folder, file), os.path.join(folder_path, file))

    os.rmdir(output_folder)
    print(f"🩹 {os.path.basename(folder_path)}: фильтрация завершена, осталось {kept} фото")

def clean_hotel_name(raw):
    name = re.sub(r'\(.*?\)', '', raw)
    name = re.sub(r'\d\*\s*', '', name)
    return name.strip()

def process_hotel(hotel_name_raw):
    if gallery_exists(hotel_name_raw):
        print(f"⏭ Отель уже обработан, пропускаем: {hotel_name_raw}")
        return

    hotel_name = clean_hotel_name(hotel_name_raw)
    print(f"\n🏨 Обработка отеля: {hotel_name_raw} → {hotel_name}")
    try:
        url = get_booking_url_by_hotel_name(hotel_name)
        if url:
            print(f"🔗 Получен URL: {url}")
            scrape_booking_photos(url, hotel_name_raw)

            folder = sanitize_folder_name(hotel_name_raw)
            gallery_path = os.path.join("data", folder, "gallery")
            if os.path.exists(gallery_path):
                filter_and_deduplicate(gallery_path)
        else:
            print(f"❌ Не удалось найти отель: {hotel_name}")
    except Exception as e:
        print(f"❌ Ошибка при обработке отеля {hotel_name_raw}: {e}")

if __name__ == "__main__":
    json_path = "data/filter.json"

    if not os.path.exists(json_path):
        print(f"❌ Файл не найден: {json_path}")
        exit()

    with open(json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"❌ Ошибка чтения JSON: {e}")
            exit()

    hotel_names = list({item.get("hotel", "").strip() for item in data if item.get("hotel")})
    print(f"🔎 Найдено {len(hotel_names)} уникальных отелей")

    for hotel in hotel_names:
        if hotel:
            process_hotel(hotel)
