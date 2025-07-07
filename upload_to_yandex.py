import os
import requests
from requests.auth import HTTPBasicAuth

# ==== НАСТРОЙКИ ====
YANDEX_USER = "oleshella@yandex.kz"
YANDEX_PASSWORD = "ydnybqhzlgggieka"
YANDEX_FOLDER = "nika_photos"  # Подпапка на Яндекс.Диске
LOCAL_FOLDER = "static/img"    # Папка, где лежат фотки локально

# ==== ФУНКЦИЯ ЗАГРУЗКИ ====
def upload_image_to_yandex(local_path, remote_name):
    url = f"https://webdav.yandex.ru/{YANDEX_FOLDER}/{remote_name}"
    with open(local_path, 'rb') as f:
        response = requests.put(url, data=f, auth=HTTPBasicAuth(YANDEX_USER, YANDEX_PASSWORD))
    if response.status_code == 201 or response.status_code == 204:
        return f"https://disk.yandex.kz/d/XTfQVMFjFSUQ7A/files/{remote_name}"
    else:
        print(f"❌ Ошибка загрузки {remote_name}: {response.status_code}")
        return None

# ==== ГЛАВНАЯ ТОЧКА ====
def upload_all_images(folder_path):
    uploaded = []
    already_uploaded = set()
    cache_file = "data/yandex_uploaded.txt"

    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            already_uploaded = set(line.strip() for line in f)

    uploaded = []
    for filename in os.listdir(LOCAL_FOLDER):
        if filename in already_uploaded:
            print(f"⏭ Пропускаем уже загруженное: {filename}")
            continue
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            local_path = os.path.join(LOCAL_FOLDER, filename)
            print(f"⬆ Загрузка {filename}...")
            link = upload_image_to_yandex(local_path, filename)
            if link:
                print(f"✅ Загружено: {link}")
                uploaded.append((filename, link))
                with open(cache_file, "a", encoding="utf-8") as f:
                    f.write(filename + "\n")
    return uploaded

# ==== ЗАПУСК ====
# if __name__ == "__main__":
#     results = upload_all_images()
#     print("\\n📦 Загрузили файлы:")
#     for local, link in results:
#         print(f"{local} → {link}")

