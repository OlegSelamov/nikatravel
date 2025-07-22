FROM mcr.microsoft.com/playwright/python:v1.46.0-focal

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

CMD ["gunicorn", "-b", "0.0.0.0:${PORT}", "app:app"]

