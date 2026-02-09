
import requests
from bs4 import BeautifulSoup
import logging
import time
import re
from urllib.parse import quote

logger = logging.getLogger("parser_logger")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/"
}

def build_booking_search_url(hotel_name):
    query = urllib.parse.quote(hotel_name)
    return f"https://www.booking.com/searchresults.ru.html?ss={query}"

def clean_query(hotel_name, country=""):
    q = f"{hotel_name} {country}".strip()
    q = re.sub(r"\d+\*", "", q)
    q = re.sub(r"\(.*?\)", "", q)
    q = re.sub(r"[,*]", "", q)
    q = re.sub(r"\s{2,}", " ", q)
    return q.strip()

def get_booking_url_by_hotel_name(hotel_name, country=""):
    query = clean_query(hotel_name, country)
    search_url = f"https://html.duckduckgo.com/html/?q={quote(query + ' site:booking.com')}"
    logger.info(f"🔎 DuckDuckGo поиск: {query}")

    try:
        r = requests.get(search_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            logger.warning(f"❌ DuckDuckGo вернул код: {r.status_code}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        results = soup.select("a.result__a[href]")
        for a in results:
            href = a["href"]
            if "booking.com/hotel" in href and not "searchresults" in href:
                clean_href = href.split("&")[0]
                logger.info(f"✅ Найдено через DuckDuckGo: {clean_href}")
                return clean_href
        logger.warning("⚠️ DuckDuckGo не дал подходящей ссылки")
    except Exception as e:
        logger.error(f"❌ Ошибка DuckDuckGo: {e}")

    return None
