FROM mcr.microsoft.com/playwright/python:v1.46.0-focal

WORKDIR /app

# Копируем все файлы проекта
COPY . /app

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Chromium для Playwright
RUN playwright install chromium

# Убедимся, что важные папки скопированы
COPY templates /app/templates
COPY static /app/static
COPY data /app/data

# Запускаем Flask напрямую для проверки
CMD ["python", "app.py"]
