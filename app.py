import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from threading import Thread 
from flask import Flask, render_template, request, redirect, url_for, session, flash
from kazunion_fetch import run
import threading
import os
import json
import requests
import subprocess
from werkzeug.utils import secure_filename
import logging

app = Flask(__name__)
app.secret_key = 'supersecretkey'

app.config['UPLOAD_FOLDER'] = os.path.join('static', 'img')

# ==================== НАСТРОЙКА ЛОГГЕРА ====================
logging.basicConfig(
    filename="parser.log",
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

# Загрузка туров
def load_tours():
    if os.path.exists(FILTER_FILE):
        with open(FILTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
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
    return render_template('frontend/index.html', tours=tours, places=places, news=news, hotels=hotels, banners=banners)

@app.route('/about')
def about():
    return render_template('frontend/about.html')

@app.route('/contacts')
def contacts():
    return render_template('frontend/contacts.html')

@app.route('/filter')
def filter_page():
    tours = load_tours()
    return render_template('frontend/filter.html', tours=tours)

@app.route('/tour/<int:tour_id>')
def tour_detail(tour_id):
    tours = load_tours()
    if 0 <= tour_id < len(tours):
        return render_template('frontend/tour_detail.html', tour=tours[tour_id], tour_id=tour_id)
    else:
        return "Тур не найден", 404

# Обработка бронирования тура
@app.route('/confirmation/<int:tour_id>')
def confirmation_page(tour_id):
    with open('data/filter.json', encoding='utf-8') as f:
        tours = json.load(f)
    tour = tours[tour_id]

    # Получаем из query ?tourists=1&nights=5&total_price=500000
    tourists = request.args.get('tourists', tour['seats'])
    nights = request.args.get('nights', tour['nights'])
    total_price = request.args.get('total_price', tour['price'])

    return render_template(
        'frontend/booking_confirmation.html',
        tour=tour,
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
    tour = tours[tour_id] if 0 <= tour_id < len(tours) else None

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

    return render_template('frontend/thank_you.html')  

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
        config['nights'] = [int(request.form.get('nights') or 7)]
        config['meal'] = request.form.getlist('meal')
        config['currency'] = request.form.get('currency')
        config['limit'] = int(request.form.get('limit') or 10)
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
        with open('parser.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()[-300:]  # последние 300 строк
        return ''.join(lines)
    except:
        return 'Лог-файл не найден или пуст.'
  
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
    if request.method == 'POST':
        title = request.form['title']
        image_file = request.files['image']

        banners = load_json(BANNERS_FILE)

        if image_file:
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, image_filename))
        else:
            image_filename = ""

        new_banner = {
            'title': title,
            'image': image_filename
        }
        banners.append(new_banner)
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
