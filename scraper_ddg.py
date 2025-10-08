import requests
from bs4 import BeautifulSoup
import logging, time, re
from urllib.parse import quote, urlparse, urlunparse

logger = logging.getLogger("parser_logger")

DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/"
}
MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-G996B) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/"
}

def clean_hotel_query(hotel_name, country=""):
    q = f"{hotel_name} {country}".strip()
    q = re.sub(r"\d+\*", "", q)          # убираем '5*'
    q = re.sub(r"\(.*?\)", "", q)        # убираем '(город)'
    # при желании почисти страны:
    q = re.sub(r"\b(Vietnam|Вьетнам|Turkey|Турция)\b", "", q, flags=re.I).strip()
    # сжимаем двойные пробелы
    q = re.sub(r"\s{2,}", " ", q)
    return q

def _pick_first_hotel_link(html, base):
    soup = BeautifulSoup(html, "html.parser")
    # 1) сначала пробуем «новую» разметку десктопа
    a = soup.select_one('a[data-testid="title-link"]')
    if a and a.get("href"):
        href = a["href"]
        return href if href.startswith("http") else (base + href)

    # 2) fallback: находим первую ссылку, где есть /hotel/
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if "/hotel/" in href:
            return href if href.startswith("http") else (base + href)

    return None

def _normalize_booking_url(url):
    """Делаем URL каноничным и принудительно на русском"""
    try:
        # отрезаем query/фрагмент, оставляем путь
        parsed = urlparse(url)
        clean = urlunparse((parsed.scheme or "https", parsed.netloc or "www.booking.com",
                            parsed.path, "", "", ""))
        # если нет .ru.html — добавим lang=ru
        if not clean.endswith(".ru.html"):
            # некоторые ссылки уже имеют ? — добавим &lang=ru
            sep = "&" if "?" in url else "?"
            return clean + sep + "lang=ru"
        return clean
    except Exception:
        return url

def get_booking_url_by_hotel_name(hotel_name, country=""):
    """Ищем отель напрямую на Booking: сначала мобилка, потом десктоп. Без Duck."""
    query = clean_hotel_query(hotel_name, country)
    logger.info(f"🔎 Booking поиск (чистый запрос): {query}")

    # Пауза, чтобы снизить шанс 202
    time.sleep(2)

    # 1) Мобильная выдача — менее «злая»
    mobile_urls = [
        f"https://m.booking.com/searchresults.ru.html?ss={quote(query)}",
        f"https://m.booking.com/search.html?ss={quote(query)}",              # запасной путь мобилки
    ]
    for su in mobile_urls:
        try:
            r = requests.get(su, headers=MOBILE_HEADERS, timeout=20)
            if r.status_code == 200 and r.text:
                link = _pick_first_hotel_link(r.text, "https://m.booking.com")
                if link:
                    norm = _normalize_booking_url(link.replace("https://m.booking.com", "https://www.booking.com"))
                    logger.info(f"✅ Найдено через мобилку: {norm}")
                    return norm
            else:
                logger.warning(f"⚠️ Мобилка вернула {r.status_code} для {su}")
        except Exception as e:
            logger.warning(f"❗ Ошибка мобилки {su}: {e}")

    # 2) Десктоп как резерв (может дать 202, но попробуем 1–2 раза c бэкоффом)
    desktop_url = f"https://www.booking.com/searchresults.ru.html?ss={quote(query)}"
    for attempt in range(2):
        try:
            if attempt:
                time.sleep(2.5 + attempt)  # небольшой бэкофф
            r = requests.get(desktop_url, headers=DESKTOP_HEADERS, timeout=20)
            if r.status_code != 200:
                logger.error(f"❌ Десктоп вернул {r.status_code} (attempt {attempt+1})")
                continue
            link = _pick_first_hotel_link(r.text, "https://www.booking.com")
            if link:
                norm = _normalize_booking_url(link)
                logger.info(f"✅ Найдено через десктоп: {norm}")
                return norm
        except Exception as e:
            logger.warning(f"❗ Ошибка десктопа (attempt {attempt+1}): {e}")

    logger.warning("⚠️ Booking не дал ссылку ни через мобилку, ни через десктоп")
    return None
