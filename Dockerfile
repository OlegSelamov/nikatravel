
# Используем официальный образ Playwright с Python
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем все файлы проекта
COPY . /app

# Устанавливаем зависимости
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    playwright install

# Указываем порт (если ты запускаешь Flask-сервер)
EXPOSE 5000

# Запуск приложения
CMD ["python", "app.py"]
