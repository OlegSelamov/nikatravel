# Используем готовый образ от Microsoft с Chromium
FROM mcr.microsoft.com/playwright/python:v1.53.1-jammy

# Устанавливаем зависимости
WORKDIR /app
COPY . /app

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт (если нужно)
EXPOSE 10000

# Запускаем твой парсер
CMD ["python", "kazunion_fetch.py"]
