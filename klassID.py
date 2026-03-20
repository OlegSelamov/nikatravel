import json
import time

with open("data/offers.json", encoding="utf-8") as f:
    offers = json.load(f)

changed = False

for o in offers:
    if not o.get("id"):
        o["id"] = int(time.time() * 1000)
        changed = True
        time.sleep(0.001)

if changed:
    with open("data/offers.json", "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)

print("ID добавлены")
