import subprocess
import json
import os

CONFIG_PATH = 'data/filter_config.json'

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def run_script(script_name, args=None):
    cmd = ['python', script_name]
    if args:
        cmd += args
    subprocess.run(cmd, check=True)

if __name__ == '__main__':
    try:
        config = load_config()
        # Преобразуем дату из YYYY-MM-DD в DD.MM.YYYY
        if 'departure_date' in config:
            parts = config['departure_date'].split('-')
            if len(parts) == 3:
                config['departure_date'] = f"{parts[2]}.{parts[1]}.{parts[0]}"
            else:
                print("Неверный формат даты: ", config['departure_date'])
                config['departure_date'] = "дата_ошибка"

        # Сохраняем конфиг как аргументы в kazunion_config.json
        with open('kazunion_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print("Запуск: Kazunion Fetch")
        run_script('kazunion_fetch.py')

        print("\nЗапуск: HTML -> JSON")
        run_script('parserhtml.py')

        print("\nЗапуск: Фото и описание")
        run_script('booking_scraper_vlite_plus.py')

        print("\nПарсинг завершён успешно!")

    except subprocess.CalledProcessError as e:
        print(f"Ошибка выполнения: {e}")