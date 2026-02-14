import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from threading import Thread 
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
from kazunion_fetch import run
from flask import jsonify
import hashlib
import threading
import os
import json
import requests
import subprocess
import uuid
import time
from werkzeug.utils import secure_filename
from flask import send_from_directory
import logging

# Отключаем стандартные логи Flask/Werkzeug
log = logging.getLogger('werkzeug')
log.disabled = True

app = Flask(__name__)
OFFERS_PATH = os.path.join("data", "offers.json")
HOTELS_PATH = os.path.join("data", "hotels.json")
app.secret_key = 'supersecretkey'

app.config['UPLOAD_FOLDER'] = os.path.join('static', 'img')

# ==================== НАСТРОЙКА ЛОГГЕРА ====================
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parser.log")

logging.basicConfig(
    filename=LOG_FILE,
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Пути
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
IMAGE_FOLDER = os.path.join(STATIC_FOLDER, 'img')
OFFERS_FILE = os.path.join(DATA_FOLDER, 'offers.json')      # было filter.json
HOTEL_DETAILS_FILE = os.path.join(DATA_FOLDER, 'hotels.json')  # новый hotels.json (dict hotel_id -> data)
HOTELS_SITE_FILE = os.path.join(DATA_FOLDER, 'hotels_site.json')  # старые “рекомендуемые отели” (list)
PLACES_FILE = os.path.join(DATA_FOLDER, 'places.json')
NEWS_FILE = os.path.join(DATA_FOLDER, 'news.json')
HOTELS_FILE = HOTELS_SITE_FILE
BANNERS_FILE = os.path.join(DATA_FOLDER, 'banners.json')

def load_json(path, default):
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения JSON {path}: {e}")
        return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# === НАСТРОЙКИ TELEGRAM ===
TELEGRAM_TOKEN = '8198089868:AAFJndPCalVaUBhmKEUAv7qrUpkcOs52XEY'
TELEGRAM_CHAT_ID = '1894258213'

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_LOGIN = "nikatravel26@gmail.com"
SMTP_PASSWORD = "tjvh vcmo yazi qenn"

REQUESTS_FILE = os.path.join(DATA_FOLDER, 'requests.json')

def load_requests():
    if os.path.exists(REQUESTS_FILE):
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_requests(data):
    with open(REQUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
FAVORITES_FILE = os.path.join(DATA_FOLDER, 'favorites.json')

def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_favorites(data):
    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ====== OFFERS / HOTELS (новая схема данных) ======

def load_offers():
    if os.path.exists(OFFERS_FILE):
        with open(OFFERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_offers(offers):
    with open(OFFERS_FILE, "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)

def load_hotel_details():
    """hotels.json (dict): {hotel_id: {...}}"""
    if os.path.exists(HOTEL_DETAILS_FILE):
        with open(HOTEL_DETAILS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    return {}

def enrich_offers_with_hotels(offers, hotels_by_id):
    """Для карточек: добавляем image/gallery/description из hotels.json"""
    out = []
    for idx, o in enumerate(offers):
        hotel_id = o.get("hotel_id")
        h = hotels_by_id.get(hotel_id, {}) if hotel_id else {}

        merged = {**o, **h}

        # ✅ 1) ГАРАНТИРУЕМ ID (иначе /tour/undefined -> 404)
        if merged.get("id") in (None, "", "undefined"):
            # стабильный id по hotel_id, чтобы не менялся
            # (а не time.time(), иначе будут ломаться ссылки/избранное)
            base = hotel_id or str(idx)
            stable_id = hashlib.md5(base.encode("utf-8")).hexdigest()[:10]
            merged["id"] = int(stable_id, 16)

        # ✅ 2) Нормализуем nights в int (у тебя строка "7")
        try:
            merged["nights"] = int(merged.get("nights") or 0)
        except:
            merged["nights"] = 0

        # ✅ 3) гарантируем image/gallery/description чтобы шаблоны не падали
        if not merged.get("image"):
            merged["image"] = ""
        if not merged.get("gallery"):
            merged["gallery"] = [merged["image"]] if merged.get("image") else []
        if not merged.get("description"):
            merged["description"] = ""

        out.append(merged)
    return out

# ===========================
# Маршруты основного сайта
# ===========================

@app.route('/place/<int:id>')
def place_detail(id):
    places = load_json(PLACES_FILE)
    if 0 <= id < len(places):
        return render_template('frontend/place_detail.html', place=places[id])
    else:
        return "Место не найдено", 404

@app.route('/news/<int:id>')
def news_detail(id):
    news_list = load_json(NEWS_FILE)
    if 0 <= id < len(news_list):
        return render_template('frontend/news_detail.html', news=news_list[id])
    else:
        return "Новость не найдена", 404

@app.route('/hotel/<int:id>')
def hotel_detail(id):
    hotels = load_json(HOTELS_FILE)
    if 0 <= id < len(hotels):
        return render_template('frontend/hotel_detail.html', hotel=hotels[id])
    else:
        return "Отель не найден", 404

@app.route('/')
def index():
    # 📦 Загружаем данные
    offers = load_offers()
    hotels_by_id = load_hotel_details()

    # 🔗 Обогащаем офферы данными отелей
    tours = enrich_offers_with_hotels(offers, hotels_by_id)

    # 🔐 ОСТАВЛЯЕМ ТОЛЬКО КОРРЕКТНЫЕ ТУРЫ С ID
    # ЭТО КРИТИЧЕСКИ ВАЖНО
    tours = [
        t for t in tours
        if isinstance(t, dict) and 'id' in t and t.get('id') is not None
    ]

    # 🔥 ГОРЯЩИЕ ТУРЫ (по скидке или старой цене)
    hot_tours = [
        t for t in tours
        if (
            str(t.get("discount_percent", "")).isdigit()
            and int(t.get("discount_percent")) >= 10
        )
        or (
            t.get("old_price") is not None
            and t.get("price") is not None
            and str(t.get("old_price")).isdigit()
            and str(t.get("price")).isdigit()
            and int(t["old_price"]) > int(t["price"])
        )
    ][:4]

    # 🧠 ID уже показанных туров
    hot_ids = {t['id'] for t in hot_tours}

    # 🇰🇿 ТУРЫ ПО КАЗАХСТАНУ (без повторов)
    kazakhstan_tours = [
        t for t in tours
        if (
            t.get("city", "").lower() in ["алматы", "астана", "шымкент"]
            and t['id'] not in hot_ids
        )
    ][:4]

    # 🧱 Контентные блоки
    places = load_json(PLACES_FILE, default=[])
    news = load_json(NEWS_FILE, default=[])
    hotels = load_json(HOTELS_FILE, default=[])
    banners = load_json(BANNERS_FILE, default=[])

    # 🎨 Рендер главной
    return render_template(
        'frontend/index.html',
        tours=tours,
        hot_tours=hot_tours,
        kazakhstan_tours=kazakhstan_tours,
        places=places,
        news=news,
        hotels=hotels,
        banners=banners,
        active_page='home'
    )

@app.route('/about')
def about():
    return render_template('frontend/about.html')

@app.route('/profile')
def profile():
    if not session.get('user'):
        return redirect(url_for('login'))

    all_requests = load_requests()
    user_requests = [
        r for r in all_requests
        if r.get('user_id') == session['user']['id']
    ]

    stats = {
        "requests": len(user_requests),
        "active": len([r for r in user_requests if r['status'] != 'Подтверждена']),
        "completed": len([r for r in user_requests if r['status'] == 'Подтверждена'])
    }

    return render_template(
        'frontend/profile.html',
        user=session['user'],
        stats=stats,
        active_page='profile'
    )
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')

        session['user'] = {
            "id": phone,
            "name": "Клиент",
            "phone": phone
        }

        # 🔥 ЕСЛИ логин из шторки — ТОЛЬКО JSON
        if request.headers.get('X-Sheet'):
            return jsonify({"success": True})

        # обычный вход
        return redirect(url_for('profile'))

    return render_template('frontend/login.html')

@app.route('/my-requests')
def my_requests():
    if not session.get('user'):
        return redirect(url_for('login'))

    all_requests = load_requests()
    user_requests = [
        r for r in all_requests
        if r['user_id'] == session['user']['id']
    ]

    return render_template(
        'frontend/my_requests.html',
        requests=user_requests,
        active_page='requests'
    )

@app.route('/request/<request_id>')
def request_detail(request_id):
    if not session.get('user'):
        return redirect(url_for('login'))

    all_requests = load_requests()

    request_item = next(
        (r for r in all_requests if r.get('id') == request_id),
        None
    )

    if not request_item:
        return "Заявка не найдена", 404

    # защита: только владелец
    if request_item['user_id'] != session['user']['id']:
        return "Доступ запрещён", 403

    return render_template(
        'frontend/request_detail.html',
        order=request_item
    )
    
@app.route('/add-to-favorites/<tour_id>')
def add_to_favorites(tour_id):
    if not session.get('user'):
        return redirect(url_for('login'))

    favorites = load_favorites()

    # защита от дублей
    exists = any(
        f['tour_id'] == tour_id and f['user_id'] == session['user']['id']
        for f in favorites
    )

    if not exists:
        favorites.append({
            "user_id": session['user']['id'],
            "tour_id": int(tour_id)
        })
        save_favorites(favorites)

    return redirect(request.referrer or '/favorites')

@app.route('/favorites')
def favorites():
    if not session.get('user'):
        return redirect(url_for('login'))

    favorites = load_favorites()
    offers = load_offers()
    hotels_by_id = load_hotel_details()
    tours = enrich_offers_with_hotels(offers, hotels_by_id)  # 🔥 ВАЖНО

    user_fav_ids = {
        f['tour_id']
        for f in favorites
        if f['user_id'] == session['user']['id']
    }

    favorite_tours = [
        t for t in tours
        if t.get('id') in user_fav_ids
    ]

    return render_template(
        'frontend/favorites.html',
        tours=favorite_tours,
        active_page='favorites'
    )

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))
    
@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        form = request.form

        title = f"Трансфер • {form.get('from')} → {form.get('to')}"

        transfer_request = {
            "id": f"tr_{int(time.time())}",
            "type": "transfer",
            "user_id": session['user']['id'],

            # 🔥 ОБЩИЕ ПОЛЯ
            "title": title,
            "image": None,
            "price": None,
            "currency": "USD",
            "status": "Новый",
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M'),

            # 🧩 СПЕЦИФИКА
            "from": form.get('from'),
            "to": form.get('to'),
            "date": form.get('date'),
            "time": form.get('time'),
            "persons": form.get('persons'),
            "car_type": form.get('car_type')
        }

        # === СОХРАНЕНИЕ В JSON ===
        all_requests = load_requests()
        all_requests.append(transfer_request)
        save_requests(all_requests)

        # === ОТПРАВКА В TELEGRAM (КАК В ОСТАЛЬНЫХ МЕСТАХ ПРОЕКТА) ===
        message = (
            "🚐 НОВЫЙ ТРАНСФЕР\n\n"
            f"Откуда: {transfer_request['from']}\n"
            f"Куда: {transfer_request['to']}\n"
            f"Дата: {transfer_request['date']}\n"
            f"Время: {transfer_request['time']}\n"
            f"Пассажиры: {transfer_request['persons']}\n"
            f"Авто: {transfer_request['car_type']}\n\n"
            f"📞 Клиент: {transfer_request['user_id']}"
        )

        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message
                },
                timeout=5
            )
        except Exception as e:
            print("Telegram error:", e)

        return redirect('/my-requests')

    return render_template(
        'frontend/transfer.html',
        active_page='transfer'
    )
  
# ======== АВИАБИЛЕТЫ ========
API_TOKEN = "ffd20ef2003810e413ac023a2e9dd5ff"
MARKER = "664464"

def build_aviasales_link(origin: str, destination: str, departure_at: str, adults: int = 1, marker: str = "") -> str:
    if not departure_at or "-" not in departure_at:
        return ""
    y, m, d = departure_at.split("T")[0].split("-")
    search_hash = f"{origin}{d}{m}{destination}{adults}"
    url = f"https://www.aviasales.kz/search/{search_hash}"
    return f"{url}?marker={marker}" if marker else url

@app.route("/flights", methods=["GET", "POST"])
def flights():
    flights = None
    origin = destination = depart_date = None

    if request.method == "POST":
        origin = request.form.get("origin")
        destination = request.form.get("destination")
        depart_date = request.form.get("depart_date")

        url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
        params = {
            "origin": origin,
            "destination": destination,
            "departure_at": depart_date,
            "currency": "rub",
            "token": API_TOKEN
        }
        r = requests.get(url, params=params)
        data = r.json()

        if data.get("data"):
            flights = sorted(data["data"], key=lambda x: x["price"])

            # Добавляем ссылку на бронирование
            for f in flights:
                f["link"] = f"https://www.aviasales.kz{f['link']}&marker={MARKER}"

    return render_template("frontend/flights.html",
                           flights=flights,
                           origin=origin,
                           destination=destination,
                           depart_date=depart_date)

@app.route("/booking")
def booking():
    origin = request.args.get("origin", "").strip()
    destination = request.args.get("destination", "").strip()
    depart_date = request.args.get("depart_date")
    adults = request.args.get("adults", "1")
    children = request.args.get("children", "0")
    infants = request.args.get("infants", "0")
    marker = "664464"  # твой партнёрский код Aviasales

    def get_iata(city_name):
        """Конвертация названия города в IATA-код через API Travelpayouts"""
        url = f"https://autocomplete.travelpayouts.com/places2?term={city_name}&locale=ru"
        try:
            r = requests.get(url, timeout=5)
            data = r.json()
            if data and "code" in data[0]:
                return data[0]["code"]
        except:
            pass
        return city_name  # если не нашли код, вернём то, что есть

    # Конвертируем, если это не код IATA (IATA всегда 3 буквы)
    if len(origin) != 3:
        origin = get_iata(origin)
    if len(destination) != 3:
        destination = get_iata(destination)

    # Форматируем дату
    date_obj = datetime.strptime(depart_date, "%Y-%m-%d")
    depart_str = date_obj.strftime("%d%m")

    # Генерируем ссылку Aviasales
    avia_url = f"https://www.aviasales.kz/search/{origin}{depart_str}{destination}?adults={adults}&children={children}&infants={infants}&marker={marker}"

    return render_template("frontend/booking.html", 
                           avia_url=avia_url, 
                           origin=origin, 
                           destination=destination, 
                           depart_date=depart_date)
                           

MARKER = "664464"

@app.route("/avia_frame")
def avia_frame():
    origin = request.args.get("origin")
    destination = request.args.get("destination")
    depart_date = request.args.get("depart_date")

    # Форматируем дату для ссылки Aviasales
    date_obj = datetime.strptime(depart_date, "%Y-%m-%d")
    depart_str = date_obj.strftime("%d%m")

    avia_url = f"https://www.aviasales.kz/search/{origin}{depart_str}{destination}?marker={MARKER}"

    return render_template("frontend/avia_frame.html", avia_url=avia_url)


@app.route('/contacts')
def contacts():
    return render_template('frontend/contacts.html')
    
@app.route('/faq')
def faq():
    return render_template('frontend/faq.html')

@app.route('/filter')
def filter_page():
    offers = load_offers()
    hotels_by_id = load_hotel_details()
    tours = enrich_offers_with_hotels(offers, hotels_by_id)
    return render_template('frontend/filter.html', tours=tours)

@app.route("/tour/<int:tour_id>")
def tour_detail(tour_id):
    departure_date = request.args.get("departure_date", "")

    offers = load_offers()
    hotels_by_id = load_hotel_details()

    tours = enrich_offers_with_hotels(offers, hotels_by_id)
    tour = next((t for t in tours if int(t.get("id")) == int(tour_id)), None)

    if not tour:
        return "Тур не найден", 404

    # Если в URL есть дата — подставим в tour (только для отображения)
    if departure_date:
        tour["departure_date"] = departure_date

    # Если в URL есть цена — подставим её (только для отображения)
    price_from_url = request.args.get("price")
    if price_from_url:
        try:
            price_val = float(price_from_url)
            tour["price"] = price_val
            tour["old_price"] = round(price_val * 1.20)
            tour["discount_percent"] = round((tour["old_price"] - price_val) / tour["old_price"] * 100)
            tour["price_per_month"] = round((price_val * 1.12) / 12)
        except ValueError:
            pass

    # Гарантируем наличие галереи
    if not tour.get("gallery"):
        if tour.get("image"):
            tour["gallery"] = [tour["image"]]
        else:
            tour["gallery"] = []

    return render_template("frontend/tour_detail.html", tour=tour, tour_id=tour_id)
    
@app.route('/confirmation/<int:tour_id>')
def confirmation_page(tour_id):
    departure_date = request.args.get('departure_date')
    tourists = request.args.get('tourists')
    nights = request.args.get('nights')
    total_price = request.args.get('total_price')

    offers = load_offers()
    hotels_by_id = load_hotel_details()
    tours = enrich_offers_with_hotels(offers, hotels_by_id)

    tour = next((t for t in tours if t['id'] == tour_id), None)
    if not tour:
        return "Тур не найден", 404

    return render_template(
        'frontend/booking_confirmation.html',
        tour=tour,
        departure_date=departure_date,
        tourists=tourists,
        nights=nights,
        total_price=total_price
    )

@app.route('/book/<int:tour_id>', methods=['POST'])
def booking_confirm(tour_id):
    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']
    people = request.form['people']
    comment = request.form.get('comment', '')

    offers = load_offers()
    hotels_by_id = load_hotel_details()
    offer = next((o for o in offers if o.get("id") == tour_id), None)
    hotel = hotels_by_id.get(offer.get("hotel_id"), {}) if offer else {}
    tour = {**offer, **hotel} if offer else None
    
    if not tour:
        return "Тур не найден", 404

    if tour:
        message = f"🔥 Новая заявка на тур!\n" \
                  f"🏖 Тур: {tour['city']}, {tour['country']} - {tour['hotel']}\n" \
                  f"👤 Имя: {name}\n📞 Телефон: {phone}\n📧 Email: {email}\n" \
                  f"👥 Кол-во человек: {people} 📝 Комментарий: {comment}"

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }
        response = requests.post(url, data=data)
    if email:
        try:
            s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            s.starttls()
            s.login(SMTP_LOGIN, SMTP_PASSWORD)
            m = MIMEMultipart()
            m['From'] = SMTP_LOGIN
            m['To'] = email
            m['Subject'] = "Подтверждение бронирования"
            body = f"Здравствуйте, {name}! Спасибо за бронирование {tour['hotel']} на {tour.get('nights', '')} ночей. Мы свяжемся с вами для уточнения деталей."
            m.attach(MIMEText(body, 'plain'))
            s.sendmail(SMTP_LOGIN, email, m.as_string())
            s.quit()
        except Exception as e:
            print(f"Mail error: {e}")
        print("Телега ответила:", response.status_code, response.text)

    return redirect(url_for('filter_page'))
    
@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
    tour_id = request.form.get('tour_id')

    hotel = request.form.get('hotel')
    city = request.form.get('city')
    country = request.form.get('country')
    departure_date = request.form.get('departure_date')
    tourists = request.form.get('tourists')
    nights = request.form.get('nights')
    total_price = request.form.get('total_price')
    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')

    
    offers = load_offers()
    hotels_by_id = load_hotel_details()
    tours = enrich_offers_with_hotels(offers, hotels_by_id)
    tour = next((t for t in tours if str(t.get("id")) == str(tour_id)), None)

    # === Определяем главное изображение ===
    main_image = None
    if tour:
        if tour.get("image"):
            main_image = tour["image"]
        elif tour.get("images") and len(tour["images"]) > 0:
            main_image = tour["images"][0]

    # === TELEGRAM ===
    message = f"""🔥 Новое бронирование!
    Тур: {hotel}
    Город: {city}
    Страна: {country}
    Дата вылета: {departure_date}
    Туристов: {tourists}
    Ночей: {nights}
    Цена: {total_price} ₸
    Имя: {name}
    Телефон: {phone}
    Email: {email}
    """

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    )

    # === EMAIL ===
    if email:
        try:
            s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            s.starttls()
            s.login(SMTP_LOGIN, SMTP_PASSWORD)
            m = MIMEMultipart()
            m['From'] = SMTP_LOGIN
            m['To'] = email
            m['Subject'] = "Подтверждение бронирования"
            body = f"Здравствуйте, {name}! Мы получили вашу заявку на тур {hotel}."
            m.attach(MIMEText(body, 'plain'))
            s.sendmail(SMTP_LOGIN, email, m.as_string())
            s.quit()
        except Exception as e:
            print("Mail error:", e)

    # === СОХРАНЯЕМ В МОИ ЗАЯВКИ ===
    if session.get('user'):
        all_requests = load_requests()

        title = f"{hotel} • {country}"

        all_requests.append({
            "id": str(uuid.uuid4()),
            "type": "tour",
            "user_id": session['user']['id'],

            # 🔥 ОБЩИЕ ПОЛЯ
            "title": title,
            "image": main_image,
            "price": total_price,
            "currency": "KZT",
            "status": "Отправлена",
            "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),

            # 🧩 ТУРОВЫЕ ПОЛЯ (ПОКА ОСТАЮТСЯ)
            "hotel": hotel,
            "city": city,
            "country": country,
            "departure_date": departure_date,
            "nights": nights,
            "tourists": tourists
        })

        save_requests(all_requests)

    return render_template('frontend/thank_you.html') 
    
# Маршрут для отдачи filter.json
@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory('data', filename)

@app.route("/zayavka")
def zayavka():
    return render_template("frontend/zayavka.html")
        
@app.route("/consultation", methods=["POST"])
def consultation():
    name = request.form.get("name")
    phone = request.form.get("phone")
    city = request.form.get("city")
    destination = request.form.get("destination")
    budget = request.form.get("budget")
    departure_date = request.form.get("departure_date")
    arrival_date = request.form.get("arrival_date")
    comment = request.form.get("comment")
    
    if phone:
        try:
            send_whatsapp(phone, name)
        except Exception as e:
            print("Ошибка WhatsApp:", e)


    message = f"""
📩 Новая заявка на консультацию:
👤 Имя: {name}
📞 Телефон: {phone}
🏙 Город: {city}
🌍 Направление: {destination}
💰 Бюджет: {budget}
🛫 Дата вылета: {departure_date}
🛬 Дата прилета: {arrival_date}
💬 Комментарий: {comment}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})

    return redirect(url_for("spasibo"))
    
ID_INSTANCE = "7105340473"           # 🔹 подставь свой idInstance
API_TOKEN_INSTANCE = "ae4d2f33ec9345d49b56b9bd6a297d566b6bbbfad2304da8a9"    # 🔹 подставь свой apiTokenInstance

def send_whatsapp(phone, name):
    """
    Отправка подтверждения клиенту в WhatsApp после бронирования.
    """
    # приводим номер к формату 77071234567
    phone = phone.replace("+", "").replace(" ", "").replace("-", "")

    text = (
        f"Здравствуйте, {name}! 🌴\n\n"
        "Спасибо, что обратились в *Nika Travel*.\n"
        "Мы получили вашу заявку и уже обрабатываем её.\n"
        "Наш консультант свяжется с вами в ближайшее время ✈️"
    )

    url = f"https://api.green-api.com/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN_INSTANCE}"
    payload = {"chatId": f"{phone}@c.us", "message": text}

    try:
        r = requests.post(url, json=payload, timeout=10)
        print("✅ WhatsApp сообщение отправлено:", r.status_code, r.text)
    except Exception as e:
        print("❌ Ошибка отправки WhatsApp:", e)    

@app.route("/spasibo")
def spasibo():
    return render_template("frontend/spasibo.html")
    
@app.route('/hotels', methods=['GET', 'POST'])
def hotels():
    if request.method == 'POST':
        # позже здесь будет логика подбора / отправки заявки
        pass

    return render_template(
        'frontend/hotels.html',
        active_page='hotels'
    )

@app.route('/visa')
def visa():
    return render_template('frontend/visa.html')

@app.route('/cruises')
def cruises():
    return render_template('frontend/cruises.html')

@app.route('/goods')
def goods():
    return render_template('frontend/goods.html')

@app.route('/news')
def news():
    return render_template('frontend/news.html')

# ===========================
# Админка
# ===========================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'admin':  # можно поменять пароль здесь
            session['admin_logged_in'] = True
            return redirect(url_for('admin_filter'))
    return render_template('admin/admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/filter', methods=['GET', 'POST'])
def admin_filter():
    config_path = os.path.join('data', 'kazunion_config.json')

    # Заранее загружаем или создаём пустой конфиг:
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {}

    if request.method == 'POST':
        # Читаем все поля формы:
        config['city_code'] = request.form.get('city_code')
        config['country_code'] = request.form.get('country_code')
        config['departure_date'] = request.form.get('departure_date')
        config["departure_end"] = request.form.get("departure_end")
        config['nights'] = [int(request.form.get('nights') or 7)]
        config['meal'] = request.form.getlist('meal')
        config['currency'] = request.form.get('currency')
        config['ADULT'] = request.form.get('ADULT')
        config['STARS'] = request.form.getlist('STARS')

        # Сохраняем конфиг
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
        def run_parser_in_background():
            try:
                run()  # запуск kazunion_fetch.run()
            except Exception as e:
                logging.error(f"Ошибка парсера: {e}")

        threading.Thread(target=run_parser_in_background).start()
        flash('🚀 Парсинг запущен!', 'success')
        return redirect(url_for('admin_filter'))          

        # GET-запрос — вернуть фильтр
    offers = load_offers()
    hotels_by_id = load_hotel_details()
    tours = enrich_offers_with_hotels(offers, hotels_by_id)
    return render_template('admin/filter_admin.html', config=config, tours=tours)
    
@app.route('/admin/log_text')
def admin_log_text():
    try:
        with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-300:]
        return ''.join(lines)
    except Exception as e:
        return f'Лог-файл не найден или пуст. Ошибка: {e}'
  
@app.route('/admin')
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/admin/add', methods=['GET', 'POST'])
def add_tour():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        departure_date = request.form.get('departure_date')
        city = request.form.get('city')
        country = request.form.get('country')
        nights = request.form.get('nights')
        meal = request.form.get('meal')
        price = request.form.get('price')
        hotel_id = request.form.get('hotel_id')

        if not hotel_id:
            flash("❌ Не указан hotel_id (нужен для связи с hotels.json)", "error")
            return redirect(url_for('add_tour'))

        offers = load_offers()

        new_offer = {
            "id": int(time.time()),
            "hotel_id": hotel_id,
            "city": city,
            "country": country,
            "meal": meal,
            "nights": nights,
            "dates_prices": [{"date": departure_date, "price": price}] if departure_date and price else []
        }

        offers.append(new_offer)
        save_offers(offers)
        return redirect(url_for('admin_filter'))

    return render_template('admin/add_tour.html')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit_tour(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    offers = load_offers()
    offer = next((o for o in offers if o.get("id") == id), None)
    if not offer:
        return "Тур не найден", 404

    if request.method == 'POST':
        # обновляем ТОЛЬКО offer (offers.json)
        offer['city'] = request.form.get('city')
        offer['country'] = request.form.get('country')
        offer['hotel_id'] = request.form.get('hotel_id') or offer.get('hotel_id')
        offer['nights'] = request.form.get('nights')
        offer['meal'] = request.form.get('meal')

        # dates_prices: либо обновляем первую дату, либо создаём
        departure_date = request.form.get('departure_date')
        price = request.form.get('price')

        if departure_date and price:
            dp = offer.get("dates_prices") or []
            if dp:
                dp[0]["date"] = departure_date
                dp[0]["price"] = price
            else:
                dp = [{"date": departure_date, "price": price}]
            offer["dates_prices"] = dp

        save_offers(offers)
        return redirect(url_for('admin_filter'))

    # Для формы удобно показать текущие значения
    # (описание/картинки подтянутся на странице через enrich при выводе списка)
    return render_template('admin/edit_tour.html', offer=offer, id=id)

@app.route('/admin/delete/<int:id>')
def delete_tour(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    offers = load_offers()
    offers = [o for o in offers if o.get("id") != id]
    save_offers(offers)
    return redirect(url_for('admin_filter'))
    
    # =============== МАРШРУТЫ: МЕСТА ========================
@app.route('/admin/places')
def admin_places():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    places = load_json(PLACES_FILE)
    return render_template('admin/places_admin.html', places=places)

@app.route('/admin/add_place', methods=['GET', 'POST'])
def add_place():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        title = request.form.get('title')
        image_file = request.files.get('image')
        filename = ''
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, filename))
        places = load_json(PLACES_FILE)
        places.append({'title': title, 'image': filename})
        save_json(PLACES_FILE, places)
        return redirect(url_for('admin_places'))
    return render_template('admin/add_place.html')

@app.route('/admin/edit_place/<int:id>', methods=['GET', 'POST'])
def edit_place(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    places = load_json(PLACES_FILE)
    if id >= len(places):
        return "Не найдено", 404
    if request.method == 'POST':
        title = request.form.get('title')
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, filename))
            places[id]['image'] = filename
        places[id]['title'] = title
        save_json(PLACES_FILE, places)
        return redirect(url_for('admin_places'))
    return render_template('admin/edit_place.html', place=places[id], id=id)

@app.route('/admin/delete_place/<int:id>')
def delete_place(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    places = load_json(PLACES_FILE)
    if id < len(places):
        places.pop(id)
        save_json(PLACES_FILE, places)
    return redirect(url_for('admin_places'))

# =============== МАРШРУТЫ: НОВОСТИ =======================
@app.route('/admin/news')
def admin_news():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    news_list = load_json(NEWS_FILE)
    return render_template('admin/news_admin.html', news=news_list)

@app.route('/admin/add_news', methods=['GET', 'POST'])
def add_news():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        title = request.form.get('title')
        image_file = request.files.get('image')
        filename = ''
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, filename))
        news_list = load_json(NEWS_FILE)
        news_list.append({'title': title, 'image': filename})
        save_json(NEWS_FILE, news_list)
        return redirect(url_for('admin_news'))
    return render_template('admin/add_news.html')

@app.route('/admin/edit_news/<int:id>', methods=['GET', 'POST'])
def edit_news(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    news_list = load_json(NEWS_FILE)
    if id >= len(news_list):
        return "Не найдено", 404
    if request.method == 'POST':
        title = request.form.get('title')
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, filename))
            news_list[id]['image'] = filename
        news_list[id]['title'] = title
        save_json(NEWS_FILE, news_list)
        return redirect(url_for('admin_news'))
    return render_template('admin/edit_news.html', news=news_list[id], id=id)

@app.route('/admin/delete_news/<int:id>')
def delete_news(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    news_list = load_json(NEWS_FILE)
    if id < len(news_list):
        news_list.pop(id)
        save_json(NEWS_FILE, news_list)
    return redirect(url_for('admin_news'))

# =============== МАРШРУТЫ: ОТЕЛИ ========================
@app.route('/admin/hotels')
def admin_hotels():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    hotels = load_json(HOTELS_FILE)
    return render_template('admin/hotels_admin.html', hotels=hotels)

@app.route('/admin/add_hotel', methods=['GET', 'POST'])
def add_hotel():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        price = request.form.get('price')
        images = request.files.getlist('images')

        saved_imgs = []
        for img in images:
            if img and img.filename:
                filename = secure_filename(img.filename)
                img.save(os.path.join('static/img', filename))  # сохраняем в static/img
                saved_imgs.append(filename)

        # Загружаем существующие отели
        if not os.path.exists(HOTELS_FILE):
            hotels = []
        else:
            with open(HOTELS_FILE, 'r', encoding='utf-8') as f:
                try:
                    hotels = json.load(f)
                except json.JSONDecodeError:
                    hotels = []

        new_hotel = {
            "title": title,
            "description": description,
            "price": price,
            "images": saved_imgs
        }

        hotels.append(new_hotel)

        with open(HOTELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(hotels, f, ensure_ascii=False, indent=2)

        return redirect(url_for('admin_hotels'))

    return render_template('admin/add_hotel.html')

@app.route('/admin/edit_hotel/<int:id>', methods=['GET', 'POST'])
def edit_hotel(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    hotels = load_json(HOTELS_FILE)
    if id >= len(hotels):
        return "Не найдено", 404
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, filename))
            hotels[id]['image'] = filename
        hotels[id]['name'] = name
        hotels[id]['price'] = price
        save_json(HOTELS_FILE, hotels)
        return redirect(url_for('admin_hotels'))
    return render_template('admin/edit_hotel.html', hotel=hotels[id], id=id)

@app.route('/admin/delete_hotel/<int:id>')
def delete_hotel(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    hotels = load_json(HOTELS_FILE)
    if id < len(hotels):
        hotels.pop(id)
        save_json(HOTELS_FILE, hotels)
    return redirect(url_for('admin_hotels'))
    
    # =============== БАННЕРЫ ===============

@app.route('/admin/banners')
def admin_banners():
    banners = load_json(BANNERS_FILE)
    return render_template('admin/banners_list.html', banners=banners)

@app.route('/admin/banners/add', methods=['GET', 'POST'])
def add_banner():
    banners = load_json(BANNERS_FILE)

    if request.method == 'POST':
        image = request.files['image']
        link = request.form['link']

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join('static/banners', filename))
        else:
            filename = ""

        banners.append({
            "image": filename,
            "link": link
        })

        save_json(BANNERS_FILE, banners)
        return redirect(url_for('admin_banners'))

    return render_template('admin/banner_add.html')

@app.route('/admin/banners/delete/<int:id>')
def delete_banner(id):
    banners = load_json(BANNERS_FILE)
    if 0 <= id < len(banners):
        banners.pop(id)
        save_json(BANNERS_FILE, banners)
    return redirect(url_for('admin_banners'))

def load_tours():
    if not os.path.exists(TOURS_PATH):
        return []
    with open(TOURS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/tours")
def api_tours():
    offers = load_json(OFFERS_PATH, [])
    hotels = load_json(HOTELS_PATH, {})

    result = []

    for offer in offers:
        hotel_id = offer.get("hotel_id")

        # получаем данные отеля по ключу
        hotel_data = hotels.get(hotel_id, {})

        result.append({
            "id": hotel_id,

            # данные отеля
            "hotel": hotel_data.get("hotel"),
            "country": hotel_data.get("country"),
            "image": hotel_data.get("image"),
            "gallery": hotel_data.get("gallery", []),
            "description": hotel_data.get("description"),

            # данные оффера
            "city": offer.get("city"),
            "meal": offer.get("meal"),
            "nights": int(offer.get("nights", 0)),
            "seats": offer.get("seats"),

            "price": int(offer.get("price", 0)),
            "old_price": int(offer.get("old_price", 0)),
            "discount_percent": int(offer.get("discount_percent", 0)),
            "price_per_month": int(offer.get("price_per_month", 0)),
            "installment_months": int(offer.get("installment_months", 0)),

            "dates_prices": offer.get("dates_prices", [])
        })

    return jsonify(result)
    
@app.route('/api/booking', methods=['POST'])
def api_booking():
    data = request.json

    hotel = data.get("hotel")
    price = data.get("price")
    name = data.get("name")
    phone = data.get("phone")
    email = data.get("email")
    people = data.get("people")

    message = f"""
🔥 Новая заявка из приложения!

🏨 Отель: {hotel}
💰 Цена: {price}
👤 Имя: {name}
📞 Телефон: {phone}
📧 Email: {email}
👥 Туристов: {people}
"""

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message
            },
            timeout=5
        )
    except Exception as e:
        print("Telegram error:", e)

    return jsonify({"status": "ok"})
# ===========================
# Запуск
# ===========================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
