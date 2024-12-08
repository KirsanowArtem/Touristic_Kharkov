from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField
from wtforms.validators import DataRequired
import folium
from geopy.geocoders import Nominatim

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Модель для кафе
class Cafe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)


# Форма для добавления кафе
class CafeForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    address = StringField('Address', validators=[DataRequired()])
    rating = IntegerField('Rating (1-5)', validators=[DataRequired()])
    description = TextAreaField('Description')


# Форма для отзыва
class ReviewForm(FlaskForm):
    cafe_id = IntegerField('Cafe ID', validators=[DataRequired()])
    review_text = TextAreaField('Review', validators=[DataRequired()])


@app.route('/')
def index():
    cafes = Cafe.query.all()  # Получаем все кафе из базы данных

    # Создаем карту и добавляем маркеры для кафе
    m = folium.Map(location=[49.9935, 36.2304], zoom_start=12)

    for cafe in cafes:
        folium.Marker(
            location=[cafe.latitude, cafe.longitude],
            popup=f"{cafe.name}<br>{cafe.address}<br>Рейтинг: {cafe.rating}",
        ).add_to(m)

    # Сохраняем карту в HTML файл
    m.save("templates/map.html")

    return render_template('index.html', cafes=cafes)


@app.route('/add', methods=['GET', 'POST'])
def add_cafe():
    form = CafeForm()
    if form.validate_on_submit():
        # Получаем координаты для адреса
        geolocator = Nominatim(user_agent="cafe_locator")
        location = geolocator.geocode(form.address.data)

        if location:
            new_cafe = Cafe(
                name=form.name.data,
                address=form.address.data,
                rating=form.rating.data,
                latitude=location.latitude,
                longitude=location.longitude
            )
            db.session.add(new_cafe)
            db.session.commit()
            return redirect(url_for('index'))
        else:
            return 'Адрес не найден!'

    return render_template('add_cafe.html', form=form)


@app.route('/review', methods=['GET', 'POST'])
def review():
    form = ReviewForm()
    if form.validate_on_submit():
        cafe = Cafe.query.get(form.cafe_id.data)
        if cafe:
            # Здесь можно добавить логику для сохранения отзыва
            return f"Отзыв для {cafe.name}: {form.review_text.data}"
        else:
            return 'Кафе не найдено!'
    return render_template('review.html', form=form)

"""
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)


"""
if __name__ == 'main':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

