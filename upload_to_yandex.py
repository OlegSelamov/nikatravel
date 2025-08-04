import os
import json
import boto3
from pathlib import Path

# === Настройки Cloudflare R2 ===
ACCOUNT_ID = "d7f7fb252f6479e65b7ab681afff1dde"  # Из "S3 endpoint"
ACCESS_KEY = "be4ccf2da6d742d7095a3058b89d2b81"  # Access Key ID
SECRET_KEY = "198c024b661b5d70aa21dd36abebaf546ff64f581f4f8cdcf7fcc78e075fdf12"  # Secret Access Key
BUCKET_NAME = "nikatravel-photos"  # Имя твоего бакета
PUBLIC_URL = "https://pub-d2bcce88ffcd45f692cd5ee867c9eeda.r2.dev"  # Public URL для картинок

# === Пути ===
BASE_DIR = Path(__file__).resolve().parent
IMG_DIR = BASE_DIR / "static" / "img"
FILTER_FILE = BASE_DIR / "data" / "filter.json"

# === Подключение к R2 ===
session = boto3.session.Session()
client = session.client(
    's3',
    endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

def photo_exists_in_r2(remote_name):
    """Проверка, есть ли файл уже в R2"""
    try:
        client.head_object(Bucket=BUCKET_NAME, Key=remote_name)
        return True
    except:
        return False

def upload_to_r2(local_file, remote_name):
    """Загрузка файла в Cloudflare R2"""
    try:
        client.upload_file(str(local_file), BUCKET_NAME, remote_name)
        print(f"✅ Загружено: {remote_name}")
        return f"{PUBLIC_URL}/{remote_name}"
    except Exception as e:
        print(f"❌ Ошибка загрузки {local_file}: {e}")
        return None

def update_filter_json():
    """Обновление ссылок в filter.json"""
    if not FILTER_FILE.exists():
        print("❌ filter.json не найден!")
        return

    with open(FILTER_FILE, "r", encoding="utf-8") as f:
        tours = json.load(f)

    changed = False

    for tour in tours:
        gallery = tour.get("gallery", [])
        hotel_name = tour.get("hotel", "").replace(" ", "_").replace("*", "")
        matching_photos = [p for p in os.listdir(IMG_DIR) if p.startswith(hotel_name)]

        if not matching_photos:
            print(f"⚠ Фото для {tour['hotel']} не найдены")
            continue

        photo_map = {}
        for photo in sorted(matching_photos):
            local_path = IMG_DIR / photo
            remote_path = photo
            if photo_exists_in_r2(remote_path):
                print(f"⏩ Пропускаем {photo}, уже в R2")
                # формируем ссылку без загрузки
                photo_map[photo] = f"{PUBLIC_URL}/{remote_path}"
                continue

            url = upload_to_r2(local_path, remote_path)
            if url:
                photo_map[photo] = url

        if photo_map:
            # Обновляем галерею
            tour["gallery"] = [photo_map.get(os.path.basename(str(g)), g) for g in gallery]
            # Обновляем главное фото
            if tour.get("image") and os.path.basename(tour["image"]) in photo_map:
                tour["image"] = photo_map[os.path.basename(tour["image"])]

            changed = True
            print(f"🔄 Обновлён тур: {tour['hotel']}")

    if changed:
        with open(FILTER_FILE, "w", encoding="utf-8") as f:
            json.dump(tours, f, ensure_ascii=False, indent=2)
        print("✅ filter.json обновлён.")
    else:
        print("⏹ Изменений нет.")
        
def cleanup_uploaded_images(json_path="data/filter.json", img_folder="static/img"):
    with open(json_path, "r", encoding="utf-8") as f:
        tours = json.load(f)
    
    used_files = set()
    for t in tours:
        if "image" in t and not t["image"].startswith("http"):
            used_files.add(t["image"])
        if "gallery" in t:
            for g in t["gallery"]:
                if not g.startswith("http"):
                    used_files.add(g)

    for file in os.listdir(img_folder):
        if file in used_files:
            continue
        path = os.path.join(img_folder, file)
        if os.path.isfile(path):
            os.remove(path)
            print(f"🗑 Удалено: {file}")        

if __name__ == "__main__":
    update_filter_json()
