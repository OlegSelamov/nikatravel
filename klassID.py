import json

with open('data/filter.json', 'r', encoding='utf-8') as f:
    tours = json.load(f)

# Проставим ID начиная с 1
for idx, tour in enumerate(tours, start=1):
    tour['id'] = idx

with open('data/filter.json', 'w', encoding='utf-8') as f:
    json.dump(tours, f, ensure_ascii=False, indent=2)

print(f"✅ Проставлено {len(tours)} ID")
