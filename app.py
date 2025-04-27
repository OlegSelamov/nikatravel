from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import os
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Пути
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
IMAGE_FOLDER = os.path.join(STATIC_FOLDER, 'img')
FILTER_FILE = os.path.join(DATA_FOLDER, 'filter.json')

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
# МАРШРУТЫ ОСНОВНОГО САЙТА
# ===========================

@app.route('/')
def index():
    return render_template('frontend/index.html')

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

# ===========================
# МАРШРУТЫ АДМИНКИ
# ===========================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == '12345':
            session['admin'] = True
            return redirect(url_for('filter_admin'))
    return render_template('admin/admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/filter')
def filter_admin():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    tours = load_tours()
    return render_template('admin/filter_admin.html', tours=tours)

@app.route('/admin/filter/add', methods=['GET', 'POST'])
def add_tour():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        tours = load_tours()
        image_file = request.files['image']
        image_name = secure_filename(image_file.filename) if image_file.filename else ""
        if image_name:
            image_file.save(os.path.join(IMAGE_FOLDER, image_name))
        tour = {
            "city": request.form['city'],
            "country": request.form['country'],
            "hotel": request.form['hotel'],
            "nights": int(request.form['nights']),
            "food": request.form['food'],
            "price": int(request.form['price']),
            "seats": request.form['seats'],
            "image": image_name
        }
        tours.append(tour)
        save_tours(tours)
        return redirect(url_for('filter_admin'))
    return render_template('admin/add_edit_filter.html', edit=False, tour={})

@app.route('/admin/filter/edit/<int:index>', methods=['GET', 'POST'])
def edit_tour(index):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    tours = load_tours()
    tour = tours[index]
    if request.method == 'POST':
        image_file = request.files['image']
        image_name = tour['image']
        if image_file.filename:
            image_name = secure_filename(image_file.filename)
            image_file.save(os.path.join(IMAGE_FOLDER, image_name))
        tour.update({
            "city": request.form['city'],
            "country": request.form['country'],
            "hotel": request.form['hotel'],
            "nights": int(request.form['nights']),
            "food": request.form['food'],
            "price": int(request.form['price']),
            "seats": request.form['seats'],
            "image": image_name
        })
        save_tours(tours)
        return redirect(url_for('filter_admin'))
    return render_template('admin/add_edit_filter.html', edit=True, tour=tour)

@app.route('/admin/filter/delete/<int:index>')
def delete_tour(index):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    tours = load_tours()
    if 0 <= index < len(tours):
        del tours[index]
        save_tours(tours)
    return redirect(url_for('filter_admin'))

# ===========================
# Запуск
# ===========================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

