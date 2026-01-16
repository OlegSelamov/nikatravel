import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from threading import Thread 
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
from kazunion_fetch import run
import threading
import os
import json
import requests
import subprocess
import uuid
from werkzeug.utils import secure_filename
from flask import send_from_directory
import logging

# Отключаем стандартные логи Flask/Werkzeug
log = logging.getLogger('werkzeug')
log.disabled = True

app = Flask(__name__)
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
FILTER_FILE = os.path.join(DATA_FOLDER, 'filter.json')
DATA_FOLDER = 'data'
PLACES_FILE = os.path.join(DATA_FOLDER, 'places.json')
NEWS_FILE = os.path.join(DATA_FOLDER, 'news.json')
HOTELS_FILE = os.path.join(DATA_FOLDER, 'hotels.json')
IMAGE_FOLDER = 'static/img'
BANNERS_FILE = os.path.join(DATA_FOLDER, 'banners.json')
BANNERS_FOLDER = 'static/banners'

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

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

# Загрузка туров
def load_tours():
    if os.path.exists(FILTER_FILE):
        with open(FILTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# Сохранение туров
def save_tours(tours):
    with open(FILTER_FILE, 'w', encoding='utf-8') as f:
        json.dump(tours, f, ensure_ascii=False, indent=2)

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
    tours = load_tours()
    places = load_json(PLACES_FILE)
    news = load_json(NEWS_FILE)
    hotels = load_json(HOTELS_FILE)
    banners = load_json(BANNERS_FILE)  # добавляем баннеры
    return render_template('frontend/index.html', tours=tours, places=places, news=news, hotels=hotels, banners=banners, active_page='home')

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

        # временно — без проверки
        session['user'] = {
            "id": phone,
            "name": "Клиент",
            "phone": phone
        }

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
    tours = load_tours()  # 🔥 ВАЖНО

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

@app.route('/filter')
def filter_page():
    tours = load_tours()
    return render_template('frontend/filter.html', tours=tours)

@app.route("/tour/<int:tour_id>")
def tour_detail(tour_id):
    # Получаем дату вылета из URL ?departure_date=...
    departure_date = request.args.get("departure_date", "")

    with open('data/filter.json', "r", encoding="utf-8") as f:
        tours = json.load(f)

    tour = next((t for t in tours if t.get("id") == tour_id), None)
    if not tour:
        return "Тур не найден", 404

    # Если в URL есть дата, заменим на неё
    if departure_date:
        tour["departure_date"] = departure_date
        
    # Если в URL есть цена — подставим её и пересчитаем старую цену, скидку и рассрочку
    price_from_url = request.args.get("price")
    if price_from_url:
        try:
            price_val = float(price_from_url)
            tour["price"] = price_val
            tour["old_price"] = round(price_val * 1.20)  # +20%
            tour["discount_percent"] = round((tour["old_price"] - price_val) / tour["old_price"] * 100)
            tour["price_per_month"] = round((price_val * 1.12) / 12)  # +12% и делим на 12 мес
        except ValueError:
            pass   

    # Гарантируем наличие галереи
    if "gallery" not in tour or not tour["gallery"]:
        if "image" in tour and tour["image"]:
            tour["gallery"] = [tour["image"]]
        else:
            tour["gallery"] = []

    # Передаём дату и в шаблон
    return render_template("frontend/tour_detail.html", tour=tour, tour_id=tour_id)
    
# Обработка бронирования тура
@app.route('/confirmation/<int:tour_id>')
def confirmation_page(tour_id):
    with open('data/filter.json', encoding='utf-8') as f:
        tours = json.load(f)
    tour = next((t for t in tours if t.get("id") == tour_id), None)
    if not tour:
        return "Тур не найден", 404

    # Получаем дату вылета из query или берём из тура
    departure_date = request.args.get('departure_date', tour.get('departure_date', ''))

    # Получаем остальные данные
    tourists = request.args.get('tourists', tour.get('seats', ''))
    nights = request.args.get('nights', tour.get('nights', ''))
    total_price = request.args.get('total_price', tour.get('price', ''))

    return render_template(
        'frontend/booking_confirmation.html',
        tour=tour,
        departure_date=departure_date,  # передаём дату в шаблон
        tourists=tourists,
        nights=nights,
        total_price=total_price,
        tour_id=tour_id
    )

@app.route('/book/<int:tour_id>', methods=['POST'])
def booking_confirm(tour_id):
    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']
    people = request.form['people']
    comment = request.form.get('comment', '')

    tours = load_tours()
    tour = next((t for t in tours if t.get("id") == tour_id), None)

    if tour:
        message = f"🔥 Новая заявка на тур!\n" \
                  f"🏖 Тур: {tour['city']}, {tour['country']} - {tour['hotel']}\n" \
                  f"👤 Имя: {name} 📞 Телефон: {phone}\📧 Email: {email}\n" \
                  f"👥 Кол-во человек: {people} 📝 Комментарий: {comment}"

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }
        response = requests.post
    if email:
        try:
            s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            s.starttls()
            s.login(SMTP_LOGIN, SMTP_PASSWORD)
            m = MIMEMultipart()
            m['From'] = SMTP_LOGIN
            m['To'] = email
            m['Subject'] = "Подтверждение бронирования"
            body = f"Здравствуйте, {name}! Спасибо за бронирование {tour['hotel']} на {nights} ночей. Мы свяжемся с вами для уточнения деталей."
            m.attach(MIMEText(body, 'plain'))
            s.sendmail(SMTP_LOGIN, email, m.as_string())
            s.quit()
        except Exception as e:
            print(f"Mail error: {e}")(url, data=data)
        print("Телега ответила:", response.status_code, response.text)

    return redirect(url_for('filter_page'))
    
@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
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
    
        # отправка WhatsApp подтверждения
    if phone:
        try:
            send_whatsapp(phone, name)
        except Exception as e:
            print("Ошибка WhatsApp:", e)

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
    Email: {email}"""

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    )

    if email:
        try:
            s = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            s.starttls()
            s.login(SMTP_LOGIN, SMTP_PASSWORD)
            m = MIMEMultipart()
            m['From'] = SMTP_LOGIN
            m['To'] = email
            m['Subject'] = "Подтверждение бронирования"
            body = f"Здравствуйте, {name}! Спасибо за бронирование {hotel} на {nights} ночей. Мы свяжемся с вами для уточнения деталей."
            m.attach(MIMEText(body, 'plain'))
            s.sendmail(SMTP_LOGIN, email, m.as_string())
            s.quit()
        except Exception as e:
            print(f"Mail error: {e}")
            
    # === СОХРАНЯЕМ ЗАЯВКУ ДЛЯ КЛИЕНТА ===
    if session.get('user'):
        all_requests = load_requests()

        all_requests.append({
            "id": str(uuid.uuid4()),
            "user_id": session['user']['id'],
            "hotel": hotel,
            "city": city,
            "country": country,
            "departure_date": departure_date,
            "nights": nights,
            "tourists": tourists,
            "price": total_price,
            "status": "Отправлена",
            "created_at": datetime.now().strftime("%d.%m.%Y %H:%M")
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
    tours = load_tours()
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
        departure_date = request.form['departure_date']
        city = request.form.get('city')
        country = request.form.get('country')
        hotel = request.form.get('hotel')
        nights = request.form.get('nights')
        meal = request.form.get('meal')
        seats = request.form.get('seats')
        description = request.form.get('description')
        price = request.form.get("price")
        old_price = request.form.get("old_price")
        discount_percent = request.form.get("discount_percent")
        price_per_month = request.form.get("price_per_month")
        installment_months = request.form.get("installment_months")
        image = request.form.get("image") or ""


        # Главное фото
        image_filename = ""
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, image_filename))


        # Галерея (много фото)
        gallery_files = request.files.getlist('gallery_images')
        gallery_filenames = []
        for file in gallery_files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(IMAGE_FOLDER, filename))
                gallery_filenames.append(filename)

        tours = load_tours()
        new_tour = {
    "departure_date": departure_date,
    "city": city,
    "country": country,
    "hotel": hotel,
    "nights": nights,
    "meal": meal,
    "seats": seats,
    "description": description,
    "price": price,
    "old_price": old_price,
    "discount_percent": discount_percent,
    "price_per_month": price_per_month,
    "installment_months": installment_months,
    "image": image_filename if image_filename else "",
}
        
        tours.append(new_tour)
        save_tours(tours)
        return redirect(url_for('admin_filter'))

    return render_template('admin/add_tour.html')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit_tour(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    tours = load_tours()
    if id >= len(tours):
        return "Тур не найден", 404

    tour = tours[id]

    if request.method == 'POST':
        tour['city'] = request.form.get('city')
        tour['country'] = request.form.get('country')
        tour['hotel'] = request.form.get('hotel')
        tour['nights'] = request.form.get('nights')
        tour['meal'] = request.form.get('meal')
        tour['price'] = request.form.get('price')
        tour['seats'] = request.form.get('seats')
        tour['description'] = request.form.get('description')

        # Главное фото (если загружено новое)
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, image_filename))
            tour['image'] = image_filename

        # Новые фотки в галерею
        gallery_files = request.files.getlist('gallery_images')
        for file in gallery_files:
            if file and file.filename:
                filename = sec             
                ure_filename(file.filename)
                file.save(os.path.join(IMAGE_FOLDER, filename))
                if 'gallery' not in tour:
                    tour['gallery'] = []
                tour['gallery'].append(filename)

        save_tours(tours)
        return redirect(url_for('admin_filter'))

    return render_template('admin/edit_tour.html', tour=tour, id=id)

@app.route('/admin/delete/<int:id>')
def delete_tour(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    tours = load_tours()
    if 0 <= id < len(tours):
        tours.pop(id)
        save_tours(tours)
    return redirect(url_for('admin_filter'))
    
@app.route('/admin/filter/edit/<int:index>', methods=['GET', 'POST'])
def edit_filter_tour(index):
    with open('data/filter.json', 'r', encoding='utf-8') as f:
        tours = json.load(f)

    if request.method == 'POST':
        tours[index]['departure_date'] = request.form['departure_date']
        tours[index]['city'] = request.form['city']
        tours[index]['country'] = request.form['country']
        tours[index]['hotel'] = request.form['hotel']
        tours[index]['nights'] = request.form['nights']
        tours[index]['meal'] = request.form['meal']
        tours[index]['seats'] = request.form['seats']
        tours[index]['price'] = request.form['price']

        with open('data/filter.json', 'w', encoding='utf-8') as f:
            json.dump(tours, f, ensure_ascii=False, indent=2)

        return redirect(url_for('admin_filter'))

    return render_template('admin/edit_tour.html', tour=tours[index], index=index)

@app.route('/admin/filter/delete/<int:index>')
def delete_filter_tour(index):
    with open('data/filter.json', 'r', encoding='utf-8') as f:
        tours = json.load(f)

    if 0 <= index < len(tours):
        tours.pop(index)
        with open('data/filter.json', 'w', encoding='utf-8') as f:
            json.dump(tours, f, ensure_ascii=False, indent=2)

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
    
@app.route('/hotel/<int:index>')
def hotel_detail_page(index):
    with open('data/hotels.json', 'r', encoding='utf-8') as f:
        hotels = json.load(f)
    return render_template('hotel_details.html', hotel=hotels[index])

# ===========================
# Запуск
# ===========================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
