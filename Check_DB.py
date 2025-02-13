import sqlite3

def view_data():
    # Путь к базе данных
    conn = sqlite3.connect('cafes.db')
    cursor = conn.cursor()

    # Запрос, чтобы вывести все данные из таблицы
    cursor.execute('SELECT * FROM cafes')
    rows = cursor.fetchall()

    # Вывод данных в консоль
    for row in rows:
        print(row)

    conn.close()

# Вызов функции
view_data()
