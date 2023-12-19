from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, join_room
import requests
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ioht'
socketio = SocketIO(app)

# Funktion til at oprette databasen, hvis den ikke findes
def create_database():
    db_path = '/home/ioht1/ioht/Projekt/myvenv/personale.db'  # Stien til vores database
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Opretter usertable til vores login
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()

create_database()  # Kalder funktionen for at oprette databasen, hvis den ikke eksisterer


create_database()

# Opretter forbindesen til databsen
def get_db():
    conn = sqlite3.connect('/home/ioht1/ioht/Projekt/myvenv/personale.db')
    return conn


# registrering af ny bruger 
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        new_username = request.form['new_username']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            return render_template('register.html', error='Kode stemmer ikke overens')

        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=?", (new_username,))
        existing_user = cursor.fetchone()

        if existing_user:
            return render_template('register.html', error='Brugernavn er brugt')

        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (new_username, hashed_password))
        conn.commit()
        conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')

# Login af bruger
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            return render_template('display_data.html') 

        error = 'Brugernavn eller kode er forkert'
        return render_template('login.html', error=error)

    return render_template('login.html')


# Logud
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


# Viser altid login side først
@app.route('/')
def display_data():
    return redirect(url_for('login'))



# Henter data fra modtager pie, hvis man er logget ind 
@socketio.on('request_data_update')
def handle_data_update():
    if 'user_id' in session:
        user_id = session['user_id']
        join_room(user_id)

        response = requests.get("http://192.168.2.2:5001/get_database_data")

        if response.status_code == 200:
            data = response.json()
            latest_data = data[0] if data else None
            socketio.emit('update_data', latest_data, room=user_id)
    else:
        return redirect(url_for('login'))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5002, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
