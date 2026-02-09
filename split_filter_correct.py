import json
import os
import re

SRC = "data/filter.json"
HOTELS_OUT = "data/hotels.json"
OFFERS_OUT = "data/offers.json"


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^\w]+", "_", text)
    return text.strip("_")


with open(SRC, "r", encoding="utf-8") as f:
    records = json.load(f)

hotels = {}
offers = []

for rec in records:
    hotel_name = rec.get("hotel")
    if not hotel_name:
        continue

    hotel_id = slugify(hotel_name)

    # -------- HOTELS --------
    if hotel_id not in hotels:
        hotels[hotel_id] = {
            "hotel": hotel_name,
            "country": rec.get("country"),
            "image": rec.get("image"),
            "gallery": rec.get("gallery", []),
            "description": rec.get("description"),
        }

    # -------- OFFERS --------
    offer = {
        "hotel_id": hotel_id,
        "city": rec.get("city"),
        "meal": rec.get("meal"),
        "nights": rec.get("nights"),
        "seats": rec.get("seats"),
        "price": rec.get("price"),
        "old_price": rec.get("old_price"),
        "discount_percent": rec.get("discount_percent"),
        "price_per_month": rec.get("price_per_month"),
        "installment_months": rec.get("installment_months"),
        "dates_prices": rec.get("dates_prices", []),
    }

    offers.append(offer)


os.makedirs("data", exist_ok=True)

with open(HOTELS_OUT, "w", encoding="utf-8") as f:
    json.dump(hotels, f, ensure_ascii=False, indent=2)

with open(OFFERS_OUT, "w", encoding="utf-8") as f:
    json.dump(offers, f, ensure_ascii=False, indent=2)

print(f"✅ Отелей: {len(hotels)} → hotels.json")
print(f"✅ Предложений: {len(offers)} → offers.json")
