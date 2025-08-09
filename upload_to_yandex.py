import os
import json
import boto3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Set

# === Cloudflare R2 ===
ACCOUNT_ID  = "d7f7fb252f6479e65b7ab681afff1dde"
ACCESS_KEY  = "be4ccf2da6d742d7095a3058b89d2b81"
SECRET_KEY  = "198c024b661b5d70aa21dd36abebaf546ff64f581f4f8cdcf7fcc78e075fdf12"
BUCKET_NAME = "nikatravel-photos"
PUBLIC_URL  = "https://pub-d2bcce88ffcd45f692cd5ee867c9eeda.r2.dev"

# === Paths ===
BASE_DIR    = Path(__file__).resolve().parent
IMG_DIR     = BASE_DIR / "static" / "img"
FILTER_FILE = BASE_DIR / "data" / "filter.json"

# === S3 client ===
session = boto3.session.Session()
s3 = session.client(
    "s3",
    endpoint_url=f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

def list_all_keys(bucket: str, prefix: str = "") -> Set[str]:
    """Получить множество всех ключей в бакете (быстрое последующее сравнение)."""
    keys: Set[str] = set()
    token = None
    while True:
        kwargs = {"Bucket": bucket, "MaxKeys": 1000}
        if prefix:
            kwargs["Prefix"] = prefix
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            keys.add(obj["Key"])
        if resp.get("IsTruncated"):
            token = resp.get("NextContinuationToken")
        else:
            break
    return keys

def is_url(s: str) -> bool:
    return isinstance(s, str) and (s.startswith("http://") or s.startswith("https://"))

def collect_needed_files(tours: List[dict]) -> Set[str]:
    """
    Собираем ВСЕ имена файлов (basename) из image и gallery, которые НЕ URL.
    """
    needed: Set[str] = set()
    for t in tours:
        img = t.get("image")
        if isinstance(img, str) and not is_url(img):
            needed.add(os.path.basename(img))
        for g in t.get("gallery", []):
            if isinstance(g, str) and not is_url(g):
                needed.add(os.path.basename(g))
    return needed

def upload_one(local_file: Path, remote_name: str) -> Tuple[str, bool, str]:
    try:
        s3.upload_file(str(local_file), BUCKET_NAME, remote_name)
        return remote_name, True, f"{PUBLIC_URL}/{remote_name}"
    except Exception as e:
        print(f"❌ Ошибка загрузки {local_file.name}: {e}")
        return remote_name, False, ""

def update_filter_json(max_workers: int = 10):
    if not FILTER_FILE.exists():
        print("❌ filter.json не найден!")
        return

    with open(FILTER_FILE, "r", encoding="utf-8") as f:
        tours = json.load(f)

    # 1) Собираем все требуемые не-URL файлы из JSON
    needed_files = collect_needed_files(tours)
    if not needed_files:
        print("⏹ В JSON нет локальных путей для замены (всё уже URL?).")
        return

    local_files = set(os.listdir(IMG_DIR))
    print(f"📂 Локальных файлов: {len(local_files)} | Нужны из JSON: {len(needed_files)}")

    # 2) Получаем все уже существующие ключи в бакете (мгновенный пропуск)
    existing_keys = list_all_keys(BUCKET_NAME)
    print(f"☁️  Уже в R2: {len(existing_keys)} ключей")

    # 3) Готовим список к загрузке и карту уже доступных URL
    to_upload: List[Tuple[Path, str]] = []
    url_map: Dict[str, str] = {}  # filename -> public URL

    for fname in sorted(needed_files):
        if fname not in local_files:
            print(f"⚠ Локального файла нет: {fname} (пропускаю)")
            continue
        if fname in existing_keys:
            url_map[fname] = f"{PUBLIC_URL}/{fname}"
        else:
            to_upload.append((IMG_DIR / fname, fname))

    print(f"🚀 К загрузке: {len(to_upload)} | Уже есть: {len(url_map)}")

    # 4) Параллельная загрузка недостающих
    if to_upload:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(upload_one, lf, rn) for lf, rn in to_upload]
            for fut in as_completed(futures):
                remote_name, ok, url = fut.result()
                if ok and url:
                    url_map[os.path.basename(remote_name)] = url
                    existing_keys.add(remote_name)

    # 5) Обновляем JSON: заменяем только те строки, что не URL и чьи basename есть в url_map
    changed = 0
    for t in tours:
        # image
        img = t.get("image")
        if isinstance(img, str) and not is_url(img):
            base = os.path.basename(img)
            new_url = url_map.get(base)
            if new_url and new_url != img:
                t["image"] = new_url
                changed += 1

        # gallery
        gallery = t.get("gallery", [])
        new_gallery = []
        replaced_here = False
        for g in gallery:
            if isinstance(g, str) and not is_url(g):
                base = os.path.basename(g)
                new_url = url_map.get(base, g)
                if new_url != g:
                    replaced_here = True
                new_gallery.append(new_url)
            else:
                new_gallery.append(g)
        if replaced_here:
            t["gallery"] = new_gallery
            changed += 1

    if changed > 0:
        with open(FILTER_FILE, "w", encoding="utf-8") as f:
            json.dump(tours, f, ensure_ascii=False, indent=2)
        print(f"✅ filter.json обновлён. Заменено полей: {changed}")
    else:
        print("⏹ Изменений нет — нечего было заменять.")

def cleanup_uploaded_images(json_path="data/filter.json", img_folder="static/img"):
    with open(json_path, "r", encoding="utf-8") as f:
        tours = json.load(f)

    used_files = set()
    for t in tours:
        img = t.get("image")
        if isinstance(img, str) and not is_url(img):
            used_files.add(os.path.basename(img))
        for g in t.get("gallery", []):
            if isinstance(g, str) and not is_url(g):
                used_files.add(os.path.basename(g))

    for file in os.listdir(img_folder):
        if file in used_files:
            continue
        path = os.path.join(img_folder, file)
        if os.path.isfile(path):
            os.remove(path)
            print(f"🗑 Удалено: {file}")

if __name__ == "__main__":
    update_filter_json(max_workers=10)
