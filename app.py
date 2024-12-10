import logging
import os
import sqlite3
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField
from wtforms.fields.choices import SelectField
from wtforms.fields.simple import SubmitField
from wtforms.validators import DataRequired
import folium
from geopy.geocoders import Nominatim

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
app.config['SECRET_KEY'] = 'mysecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


def init_db():
    # Создание таблицы пользователей
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            email TEXT UNIQUE,
            last_login TEXT
        )
    ''')
    conn.commit()
    conn.close()

    # Создание таблиц для кафе, ресторанов и запросов
    conn = sqlite3.connect('cafes.db')  # Новое соединение для базы данных кафе
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
            place_index TEXT NOT NULL
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
            place_index TEXT NOT NULL
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
            type TEXT NOT NULL
        )
    ''')
    conn.commit()  # Фиксируем изменения
    conn.close()   # Закрываем соединение



class Cafe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)


# Форма для добавления кафе
class CafeForm(FlaskForm):
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


# Добавить тестового пользователя при запуске приложения
def create_initial_user():
    user = User.query.filter_by(username="Kirsanov Artem").first()
    if not user:
        user = User(username="Kirsanov Artem", password="12")
        db.session.add(user)
        db.session.commit()
        print("User 'Kirsanov Artem' has been created!")


@app.route('/')
def index():
    cafes = Cafe.query.all()

    # Создаем карту и добавляем маркеры для кафе
    m = folium.Map(location=[49.9935, 36.2304], zoom_start=12)

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


@app.route('/add_place', methods=['GET', 'POST'])
def add_place():
    form = CafeForm()  # Создаём объект формы

    if form.validate_on_submit():
        name = form.name.data
        address = form.address.data
        description = form.description.data
        city = form.city.data
        region = form.region.data
        type_place = form.type.data

        # Добавляем данные в таблицу request
        conn = sqlite3.connect('cafes.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO request (name, address, description, city, region, type) VALUES (?, ?, ?, ?, ?, ?)',
                       (name, address, description, city, region, type_place))
        conn.commit()
        conn.close()

        flash('Место успешно добавлено в список на одобрение!', 'success')
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
    cursor.execute("SELECT name, address, description, city, region, type FROM request WHERE id=?", (place_id,))
    place = cursor.fetchone()

    if place:
        # Генерация индексного значения
        city = place[3].lower()
        city_index = city.replace(" ", "_")
        cursor.execute(f"SELECT COUNT(*) FROM {'cafes' if place[5] == 'кафе' else 'restaurants'} WHERE city=?", (place[3],))
        count = cursor.fetchone()[0] + 1
        place_index = f"{city_index}_{count}"

        # Добавление в соответствующую таблицу (cafes или restaurants)
        if place[5] == 'кафе':
            cursor.execute(
                "INSERT INTO cafes (name, address, description, city, region, index) VALUES (?, ?, ?, ?, ?, ?)",
                (place[0], place[1], place[2], place[3], place[4], place_index))
        else:
            cursor.execute(
                "INSERT INTO restaurants (name, address, description, city, region, index) VALUES (?, ?, ?, ?, ?, ?)",
                (place[0], place[1], place[2], place[3], place[4], place_index))

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

    # Удаляем запись из таблицы request
    conn = sqlite3.connect('cafes.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM request WHERE id=?", (place_id,))
    conn.commit()
    conn.close()

    flash('Запрос успешно отклонен.', 'success')
    return redirect(url_for('admin'))

@app.route('/approve_place', methods=['POST'])
def approve_place_handler():
    action = request.form['action']
    place_id = request.form['place_id']

    conn = sqlite3.connect('cafes.db')
    cursor = conn.cursor()

    # Получаем информацию о месте
    cursor.execute("SELECT name, address, description, city, region, type FROM request WHERE id=?", (place_id,))
    place = cursor.fetchone()

    if place and action == 'approve':
        # Генерация индексного значения
        city = place[3].lower()
        city_index = city.replace(" ", "_")
        cursor.execute(f"SELECT COUNT(*) FROM {'cafes' if place[5] == 'кафе' else 'restaurants'} WHERE city=?", (place[3],))
        count = cursor.fetchone()[0] + 1
        place_index = f"{city_index}_{count}"

        # Добавление в нужную таблицу
        if place[5] == 'кафе':
            cursor.execute(
                "INSERT INTO cafes (name, address, description, city, region, place_index) VALUES (?, ?, ?, ?, ?, ?)",
                (place[0], place[1], place[2], place[3], place[4], place_index))
        elif place[5] == 'ресторан':
            cursor.execute(
                "INSERT INTO restaurants (name, address, description, city, region, place_index) VALUES (?, ?, ?, ?, ?, ?)",
                (place[0], place[1], place[2], place[3], place[4], place_index))

        # Удаляем место из request
        cursor.execute("DELETE FROM request WHERE id=?", (place_id,))
        conn.commit()
        flash('Место успешно добавлено.', 'success')

    elif action == 'reject':
        # Если действие - отклонить, удаляем запрос
        cursor.execute("DELETE FROM request WHERE id=?", (place_id,))
        conn.commit()
        flash('Запрос успешно отклонен.', 'success')

    else:
        flash('Ошибка: место не найдено.', 'error')

    conn.close()
    return redirect(url_for('admin'))


@app.route('/show_users')
def show_users():
    users = User.query.all()
    return '<br>'.join([f"{user.username}: {user.password}" for user in users])

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form['password']
        if password == "12":
            conn = sqlite3.connect('cafes.db')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM request")
            places = cursor.fetchall()

            app.logger.debug(f"Fetched places from request: {places}")  # Добавлено для логирования

            conn.close()
            return render_template('admin_panel.html', places=[
                {
                    "id": place[0],
                    "name": place[1],
                    "address": place[2],
                    "description": place[3],
                    "city": place[4],
                    "region": place[5]
                }
                for place in places
            ])
        else:
            flash('Неверный пароль!', 'error')
            return redirect(url_for('admin'))

    return render_template('admin_login.html')

@app.route('/debug_users')
def debug_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return "<br>".join([f"ID: {user[0]}, Username: {user[1]}, Email: {user[3]}" for user in users])

"""
if __name__ == '__main__':
    init_db()
    app.run(debug=True)



"""
if __name__ == '__main__':
    import os
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


