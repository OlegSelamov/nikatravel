from pathlib import Path
from PIL import Image

SRC = Path(r"C:\PRO\NIKATRAVEL\static\knopki")          # где твои png сейчас
DST = Path(r"C:\PRO\NIKATRAVEL\static\knopki_800x600")  # куда сохранить готовые
DST.mkdir(parents=True, exist_ok=True)

TARGET_W, TARGET_H = 800, 600
TARGET_RATIO = TARGET_W / TARGET_H

def cover_resize(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    w, h = img.size
    r = w / h

    # crop to target ratio (center crop)
    if r > TARGET_RATIO:
        # too wide -> crop left/right
        new_w = int(h * TARGET_RATIO)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        # too tall -> crop top/bottom
        new_h = int(w / TARGET_RATIO)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    return img.resize((TARGET_W, TARGET_H), Image.LANCZOS)

for p in SRC.glob("*.png"):
    out = DST / p.name
    with Image.open(p) as im:
        im2 = cover_resize(im)
        im2.save(out, format="PNG", optimize=True)
    print("OK:", out)

print("\nГотово. Проверь папку:", DST)
