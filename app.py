from flask import Flask, render_template, request, redirect, url_for, session
import os
import json
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'

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
@app.route('/book/<int:tour_id>', methods=['POST'])
def book_tour(tour_id):
    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']
    people = request.form['people']
    comment = request.form.get('comment', '')

    tours = load_tours()
    tour = tours[tour_id] if 0 <= tour_id < len(tours) else None

    if tour:
        message = f"🔥 Новая заявка на тур!\n\n" \
                  f"🏖 Тур: {tour['city']}, {tour['country']} - {tour['hotel']}\n" \
                  f"👤 Имя: {name}\n📞 Телефон: {phone}\n📧 Email: {email}\n" \
                  f"👥 Кол-во человек: {people}\n📝 Комментарий: {comment}"

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }
        response = requests.post(url, data=data)
        print("Телега ответила:", response.status_code, response.text)

    return redirect(url_for('filter_page'))


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

@app.route('/admin/filter')
def admin_filter():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    tours = load_tours()
    return render_template('admin/filter_admin.html', tours=tours)

@app.route('/admin/add', methods=['GET', 'POST'])
def add_tour():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        city = request.form.get('city')
        country = request.form.get('country')
        hotel = request.form.get('hotel')
        nights = request.form.get('nights')
        meal = request.form.get('meal')
        price = request.form.get('price')
        seats = request.form.get('seats')
        description = request.form.get('description')

        # Главное фото
        image_file = request.files.get('image')
        image_filename = None
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
            "city": city,
            "country": country,
            "hotel": hotel,
            "nights": nights,
            "meal": meal,
            "price": price,
            "seats": seats,
            "image": image_filename,
            "description": description,
            "gallery": gallery_filenames
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
                filename = secure_filename(file.filename)
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
        name = request.form.get('name')
        price = request.form.get('price')
        image_file = request.files.get('image')
        filename = ''
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, filename))
        hotels = load_json(HOTELS_FILE)
        hotels.append({'name': name, 'price': price, 'image': filename})
        save_json(HOTELS_FILE, hotels)
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

# ===========================
# Запуск
# ===========================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
