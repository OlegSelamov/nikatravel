
import os
import json
from bs4 import BeautifulSoup
from pathlib import Path

HTML_DIR = Path("data/html")
OUTPUT_JSON = Path("data/kazunion_all.json")

def parse_table(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    data = []
    for row in table.find_all("tr")[1:]:
        cols = [col.get_text(strip=True) for col in row.find_all(["td", "th"])]
        if cols:
            data.append(cols)
    return data

def run():
    all_data = []
    for html_file in sorted(HTML_DIR.glob("kazunion_*.html")):
        print(f"Обработка {html_file}")
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
            table_data = parse_table(content)
            all_data.extend(table_data)

    # Убираем дубликаты
    unique_data = [list(x) for x in {tuple(row) for row in all_data}]
    print(f"Всего записей: {len(unique_data)}")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(unique_data, f, ensure_ascii=False, indent=2)
    print(f"Результат сохранён: {OUTPUT_JSON}")

if __name__ == "__main__":
    run()
