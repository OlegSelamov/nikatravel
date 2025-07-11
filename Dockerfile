# Используем рабочий официальный образ Playwright
FROM mcr.microsoft.com/playwright/python:v1.41.1-focal

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем проект
COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Открываем порт
EXPOSE 10000

# Запускаем парсер
CMD ["python", "kazunion_fetch.py"]
