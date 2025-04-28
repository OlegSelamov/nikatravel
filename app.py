from flask import Flask, render_template, request, redirect, url_for, session
import os
import json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'

UPLOAD_FOLDER = os.path.join('static', 'img')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
FILTER_FILE = os.path.join(DATA_FOLDER, 'filter.json')

def load_tours():
    if os.path.exists(FILTER_FILE):
        with open(FILTER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_tours(tours):
    with open(FILTER_FILE, 'w', encoding='utf-8') as f:
        json.dump(tours, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    tours = load_tours()
    return render_template('frontend/index.html', tours=tours)

@app.route('/filter')
def filter_page():
    tours = load_tours()
    return render_template('frontend/filter.html', tours=tours)

# ================== АДМИНКА ==================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == 'admin':
            session['logged_in'] = True
            return redirect(url_for('admin_filter'))
        else:
            return render_template('admin/admin_login.html', error='Неверный пароль')
    return render_template('admin/admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/filter')
def admin_filter():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))
    tours = load_tours()
    return render_template('admin/filter_admin.html', tours=tours)

@app.route('/admin/add', methods=['GET', 'POST'])
def admin_add_tour():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        file = request.files.get('image')
        filename = ''

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_tour = {
            "city": request.form.get('city'),
            "country": request.form.get('country'),
            "hotel": request.form.get('hotel'),
            "nights": request.form.get('nights'),
            "meal": request.form.get('meal'),
            "price": request.form.get('price'),
            "seats": request.form.get('seats'),
            "image": filename if filename else ""
        }
        tours = load_tours()
        tours.append(new_tour)
        save_tours(tours)
        return redirect(url_for('admin_filter'))

    return render_template('admin/add_tour.html')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit_tour(id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))

    tours = load_tours()

    if id < 0 or id >= len(tours):
        return "Тур не найден", 404

    if request.method == 'POST':
        file = request.files.get('image')
        filename = tours[id]['image']  # старое фото, если новое не загружаем

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        tours[id] = {
            "city": request.form.get('city'),
            "country": request.form.get('country'),
            "hotel": request.form.get('hotel'),
            "nights": request.form.get('nights'),
            "meal": request.form.get('meal'),
            "price": request.form.get('price'),
            "seats": request.form.get('seats'),
            "image": filename
        }
        save_tours(tours)
        return redirect(url_for('admin_filter'))

    tour = tours[id]
    return render_template('admin/edit_tour.html', tour=tour, id=id)

@app.route('/admin/delete/<int:id>')
def delete_tour(id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))

    tours = load_tours()
    if 0 <= id < len(tours):
        deleted = tours.pop(id)
        save_tours(tours)
        print(f"Удалён тур: {deleted['hotel']}")

    return redirect(url_for('admin_filter'))

if __name__ == '__main__':
    app.run(debug=True)
