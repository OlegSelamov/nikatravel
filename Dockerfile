FROM mcr.microsoft.com/playwright/python:v1.46.0-focal

WORKDIR /app
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Ставим браузеры Playwright
RUN playwright install chromium

# Запуск приложения через Gunicorn с подстановкой $PORT
CMD ["python", "app.py"]
