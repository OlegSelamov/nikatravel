#!/bin/bash

echo "📦 Установка зависимостей..."
pip install -r requirements.txt

echo "▶️ Установка Playwright браузеров..."
python3 -m playwright install --with-deps
