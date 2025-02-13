import logging
import os
import sqlite3
import folium
import time
import requests

from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm

from wtforms import StringField, IntegerField, TextAreaField
from wtforms.fields.choices import SelectField
from wtforms.fields.simple import SubmitField
from wtforms.validators import DataRequired

from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim


from folium.plugins import MarkerCluster


app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
app.config['SECRET_KEY'] = 'mysecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cafes.db")
USERS_DB_PATH = os.path.join(BASE_DIR, "users.db")

geolocator = Nominatim(user_agent="your_app_name", timeout=10)


def init_db():
    # Создание таблиц для кафе, ресторанов и запросов
    conn = sqlite3.connect(DB_PATH)  # Подключение с полным путём
    cursor = conn.cursor()

    # Таблица кафе
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cafes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            description TEXT,
            city TEXT NOT NULL,
            region TEXT NOT NULL,
            place_index TEXT NOT NULL,
            type TEXT NOT NULL,
            latitude REAL,
            longitude REAL
        )
    ''')

    # Таблица ресторанов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            description TEXT,
            city TEXT NOT NULL,
            region TEXT NOT NULL,
            place_index TEXT NOT NULL,
            type TEXT NOT NULL,
            latitude REAL,
            longitude REAL
        )
    ''')

    # Таблица запросов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS request (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            description TEXT,
            city TEXT NOT NULL,
            region TEXT NOT NULL,
            place_index TEXT NOT NULL,
            type TEXT NOT NULL,
            latitude REAL,
            longitude REAL
        )
    ''')
    conn.commit()
    conn.close()


class Cafe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)


# Форма для добавления кафе
class PlaceForm(FlaskForm):
    region = SelectField(
        'Область',
        choices=[('', 'Оберіть область'), ('Харківська', 'Харківська')],
        validators=[DataRequired()]
    )
    city = SelectField(
        'Місто',
        choices=[('', 'Оберіть місто'), ('Харків', 'Харків'), ('Ізюм', 'Ізюм'), ('Лозова', 'Лозова')],
        validators=[DataRequired()]
    )
    type = SelectField(
        'Тип закладу',
        choices=[('', 'Оберіть тип закладу'), ('кафе', 'Кафе'), ('ресторан', 'Ресторан')],
        validators=[DataRequired()]
    )
    name = StringField('Назва закладу', validators=[DataRequired()])
    address = StringField('Адреса', validators=[DataRequired()])
    description = TextAreaField('Опис закладу')

class ReviewForm(FlaskForm):
    cafe_id = IntegerField('Cafe ID', validators=[DataRequired()])
    review_text = TextAreaField('Review', validators=[DataRequired()])


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)  # Поле email


def geocode_address(address, city, region):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{address}, {city}, {region}",
        "format": "json",
        "addressdetails": 1,
        "limit": 1,
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data:
                # Убедимся, что результат совпадает с городом и областью
                result = data[0]
                if (result.get("address", {}).get("city", "").lower() == city.lower() and
                    result.get("address", {}).get("state", "").lower() == region.lower()):
                    return float(result["lat"]), float(result["lon"])
        # Если адрес не найден или данные не совпадают
        return None, None
    except Exception as e:
        # Логирование ошибки
        print(f"Ошибка при геокодировании: {e}")
        return None, None


# Проверьте, чтобы координаты сохранялись в базу данных

@app.route('/')
def index():
    cafes = Cafe.query.all()

    # Получаем параметры координат из URL
    latitude = request.args.get('latitude', type=float)
    longitude = request.args.get('longitude', type=float)

    # Если координаты переданы, то центрируем карту на них
    if latitude is not None and longitude is not None:
        center_lat, center_lon = latitude, longitude
    else:
        center_lat, center_lon = 49.9935, 36.2304  # Дефолтные координаты Харькова

    # Создаем карту и добавляем маркеры для кафе
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    for cafe in cafes:
        if cafe.latitude is not None and cafe.longitude is not None:
            try:
                folium.Marker(
                    location=[float(cafe.latitude), float(cafe.longitude)],
                    popup=f"{cafe.name}<br>{cafe.address}<br>Рейтинг: {cafe.rating}",
                ).add_to(m)
            except ValueError:
                app.logger.warning(f"Invalid coordinates for cafe: {cafe.name}")
        else:
            app.logger.warning(f"Skipping cafe {cafe.name}: Missing coordinates")

    m.save("templates/map.html")
    return render_template('index.html', cafes=cafes)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error_username = error_password = False
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Подключаемся к базе данных пользователей
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username=?', (username,))
        user = cursor.fetchone()
        conn.close()

        # Проверяем, найден ли пользователь
        if not user:
            error_username = True
            flash("Неверное имя пользователя", "error")
        elif user[2] != password:  # user[2] - это сохранённый пароль
            error_password = True
            flash("Неверный пароль", "error")
        else:
            # Если всё верно, сохраняем имя пользователя в сессии
            session['username'] = username
            flash("Вы успешно вошли!", "success")
            return redirect(url_for('welcome'))

    return render_template('login.html', error_username=error_username, error_password=error_password)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        email = request.form['email']

        # Проверяем совпадение паролей
        if password != confirm_password:
            flash('Пароли не совпадают', 'error')
            return render_template('signup.html', error_confirm_password=True)

        # Подключаемся к базе данных и проверяем существование пользователя
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                flash('Это имя пользователя уже занято.', 'error')
                return render_template('signup.html', error_username=True)

            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                flash('Этот email уже зарегистрирован.', 'error')
                return render_template('signup.html', error_email=True)

            # Сохраняем нового пользователя в базу данных
            cursor.execute('INSERT INTO users (username, password, email, last_login) VALUES (?, ?, ?, ?)',
                           (username, password, email, datetime.now()))
            conn.commit()

        flash('Регистрация успешна. Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/about_us')
def about_us():
    try:
        app.logger.debug("Accessed /about_us page")
        return render_template('about_us.html')
    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return "Internal Server Error", 500


@app.route('/partners', methods=['GET', 'POST'])
def partners():
    return render_template('partners.html')


@app.route('/request_places', methods=['GET', 'POST'])
def request_places():
    # Проверяем, вошел ли пользователь и является ли он "Kirsanov Artem"
    if 'username' not in session or session['username'] != "Kirsanov Artem":
        flash('Доступ запрещён!', 'error')
        return redirect(url_for('login'))  # Перенаправляем на страницу входа

    if request.method == 'POST':
        # Проверяем пароль
        password = request.form.get('password')
        user = User.query.filter_by(username="Kirsanov Artem").first()

        if user and user.password == password:
            flash('Доступ разрешён!', 'success')
            return render_template('request_places.html')  # Доступ разрешён
        else:
            flash('Неверный пароль!', 'error')
            return redirect(url_for('request_places'))  # Возвращаемся к вводу пароля

    # Отображаем страницу с вводом пароля
    return render_template('request_places_password.html')


@app.route('/reject_place', methods=['POST'])
def reject_place():
    place_id = request.form['place_id']
    category = request.form.get('category')

    # Подключаемся к базе данных
    conn = sqlite3.connect('cafes.db')
    cursor = conn.cursor()

    # Удаляем запись в зависимости от категории
    if category == "Кафе":
        cursor.execute("DELETE FROM cafes WHERE id=?", (place_id,))
    elif category == "Ресторан":
        cursor.execute("DELETE FROM restaurants WHERE id=?", (place_id,))
    else:
        flash('Неверная категория.', 'error')
        return redirect(url_for('admin', category=category))

    conn.commit()
    conn.close()

    flash('Запись успешно удалена.', 'success')
    return redirect(url_for('admin', category=category))



@app.route('/show_users')
def show_users():
    users = User.query.all()
    return '<br>'.join([f"{user.username}: {user.password}" for user in users])

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':  # Обработка входа
        password = request.form.get('password', None)

        if not password:  # Если пароль отсутствует
            flash('Пароль не предоставлен.', 'error')
            return render_template('admin_login.html')  # Возвращаем страницу с паролем

        if password == "12":  # Проверка пароля
            flash('Пароль подтверждён! Добро пожаловать в админ-панель.', 'success')
            return redirect(url_for('admin', category="Меню"))  # Редирект на Меню
        else:
            flash('Неверный пароль!', 'error')
            return render_template('admin_login.html')  # Возвращаем страницу с паролем

    # Обработка GET-запроса — отображаем разные категории
    category = request.args.get('category')
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Количество элементов на странице

    # Если категории нет, запрашиваем пароль
    if not category:
        return render_template('admin_login.html')

    # Показываем меню администратора
    if category == "Меню":
        return render_template('admin_menu.html')

    # Показываем запросы на одобрение
    if category == "Запросы":
        conn = sqlite3.connect('cafes.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, address, description, city, region, type, latitude, longitude FROM request")
        places = cursor.fetchall()
        print("Запросы на одобрение:", places)  # Печать для отладки
        conn.close()
        return render_template('admin_panel.html', places=[
            {
                "id": place[0],
                "name": place[1],
                "address": place[2],
                "description": place[3],
                "city": place[4],
                "region": place[5],
                "type": place[6],
                "latitude": place[7],
                "longitude": place[8]
            }
            for place in places
        ])

    # Обработка категории "Кафе" с пагинацией
    if category == "Кафе":
        conn = sqlite3.connect('cafes.db')
        cursor = conn.cursor()

        # Получаем общее количество записей
        cursor.execute("SELECT COUNT(*) FROM cafes")
        total_places = cursor.fetchone()[0]

        # Выборка записей для текущей страницы
        offset = (page - 1) * per_page
        cursor.execute(
            "SELECT id, name, address, description, city, region, place_index, type, latitude, longitude FROM cafes LIMIT ? OFFSET ?",
            (per_page, offset)
        )
        places = cursor.fetchall()
        conn.close()

        total_pages = (total_places + per_page - 1) // per_page  # Рассчитываем общее количество страниц

        return render_template(
            'admin_cafe.html',
            places=[
                {
                    "id": place[0],
                    "name": place[1],
                    "address": place[2],
                    "description": place[3],
                    "city": place[4],
                    "region": place[5],
                    "place_index": place[6],
                    "type": place[7],
                    "latitude": place[8],
                    "longitude": place[9]
                }
                for place in places
            ],
            page=page,
            total_pages=total_pages
        )

    # Обработка категории "Рестораны"
    if category == "Ресторан":
        conn = sqlite3.connect('cafes.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, address, description, city, region, place_index, type, latitude, longitude FROM restaurants")
        places = cursor.fetchall()
        conn.close()
        return render_template('admin_restaurant.html', places=[
            {
                "id": place[0],
                "name": place[1],
                "address": place[2],
                "description": place[3],
                "city": place[4],
                "region": place[5],
                "place_index": place[6],
                "type": place[7],
                "latitude": place[8],
                "longitude": place[9]
            }
            for place in places
        ])

    # Если ничего не выбрано, возвращаем меню
    return render_template('admin_menu.html')



@app.route('/add_place', methods=['GET', 'POST'])
def add_place():
    form = PlaceForm()

    if form.validate_on_submit():
        name = form.name.data
        address = form.address.data
        description = form.description.data
        city = form.city.data
        region = form.region.data
        type_place = form.type.data

        # Генерация place_index
        place_index = f"{region}_{city}_{name}".lower().replace(" ", "_")

        # Получаем координаты через геокодер
        latitude, longitude = geocode_address(address, city, region)
        if latitude is None or longitude is None:
            return "Не удалось получить координаты. Проверьте адрес и попробуйте снова.", 400

        # Если координаты не найдены, выдаём ошибку
        if latitude is None or longitude is None:
            flash('Не удалось найти координаты для данного адреса. Попробуйте другой адрес.', 'error')
            return render_template('add_place.html', form=form)

        print(f"Добавляем в базу: {name}, {address}, {description}, {city}, {region}, {type_place}, {place_index}, {latitude}, {longitude}")

        try:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO request (name, address, description, city, region, type, place_index, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (name, address, description, city, region, type_place, place_index, latitude, longitude)
            )
            conn.commit()
            print("Данные успешно добавлены в таблицу request")
            flash('Место успешно добавлено в список на одобрение!', 'success')
        except sqlite3.Error as e:
            print(f"Ошибка базы данных: {e}")
            flash(f'Ошибка базы данных: {e}', 'error')
        finally:
            conn.close()

        return redirect(url_for('index'))

    return render_template('add_place.html', form=form)

@app.route('/approve_place', methods=['POST'])
def approve_place():
    action = request.form['action']
    place_id = request.form['place_id']

    # Подключаемся к базе данных
    conn = sqlite3.connect('cafes.db')
    cursor = conn.cursor()

    # Получаем информацию о месте
    cursor.execute("SELECT name, address, description, city, region, type, place_index, latitude, longitude FROM request WHERE id=?", (place_id,))
    place = cursor.fetchone()

    if place:
        # Используем уже существующий place_index
        place_index = place[6]
        type_place = place[5]  # Используем тип из таблицы запроса

        # Добавление в соответствующую таблицу (cafes или restaurants)
        if type_place == 'кафе':
            cursor.execute(
                "INSERT INTO cafes (name, address, description, city, region, place_index, type, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (place[0], place[1], place[2], place[3], place[4], place_index, type_place, place[7], place[8]))
        else:
            cursor.execute(
                "INSERT INTO restaurants (name, address, description, city, region, place_index, type, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (place[0], place[1], place[2], place[3], place[4], place_index, type_place, place[8], place[9]))

        # Удаляем место из таблицы request
        cursor.execute("DELETE FROM request WHERE id=?", (place_id,))
        conn.commit()

        flash('Место добавлено успешно!', 'success')

    else:
        flash('Ошибка: место не найдено.', 'error')

    conn.close()
    return redirect(url_for('admin'))


@app.route('/review', methods=['GET', 'POST'])
def review():
    form = ReviewForm()
    if form.validate_on_submit():
        cafe = Cafe.query.get(form.cafe_id.data)
        if cafe:
            return f"Отзыв для {cafe.name}: {form.review_text.data}"
        else:
            return 'Кафе не найдено!'
    return render_template('review.html', form=form)

@app.route('/view_place')
def view_place():
    latitude = request.args.get('latitude', type=float)
    longitude = request.args.get('longitude', type=float)
    name = request.args.get('name', default="Место")

    if latitude is None or longitude is None:
        flash("Координаты не были переданы.", "error")
        return redirect(url_for('index'))  # Перенаправляем на главную страницу, если координаты не переданы

    return render_template('view_place.html', latitude=latitude, longitude=longitude, name=name)



#DEBUG

@app.route('/debug_users')
def debug_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return "<br>".join([f"ID: {user[0]}, Username: {user[1]}, Email: {user[3]}" for user in users])

@app.route('/test_request')
def test_request():
    conn = sqlite3.connect('cafes.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM request")
    places = cursor.fetchall()
    conn.close()
    return str(places)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)



"""
if __name__ == '__main__':
    import os
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

"""