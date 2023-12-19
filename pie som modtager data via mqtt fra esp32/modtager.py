from flask import Flask, jsonify
import paho.mqtt.client as mqtt
import sqlite3
import os
from datetime import datetime, timedelta
import RPi.GPIO as GPIO
import time

app = Flask(__name__)

# Konfiguere vores mqtt så vores esp32 og pie kan snakke sammen
mqtt_server = "localhost"
mqtt_port = 1883
mqtt_user = "ioht"
mqtt_password = "kasper3600"
ultrasonic_topic = "ultrasonic"
co2_topic = "co2"

# Stien til vores sqlite3 database
database_path = '/home/ioht/client/myvenv/ioht_guf1.db'
# Max rows gør så vi maks kan have 2000 kolonner og dermed ikke overfylder vores database
max_rows = 2000

# Variabler til at gemme senste data
last_distance = 0
last_co2 = 0

# konfiguration på til vores buzzer
buzzer_pin = 13
GPIO.setmode(GPIO.BCM)
GPIO.setup(buzzer_pin, GPIO.OUT)
pwm = GPIO.PWM(buzzer_pin, 1000)
pwm.start(0)

#opretter databasen, hvis den ikke eksisterer 
def initialize_database():
    if not os.path.exists(database_path):
        connection = sqlite3.connect(database_path)
        cursor = connection.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                distance REAL,
                co2 REAL,
                timestamp TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
            )
        ''')

        connection.commit()
        connection.close()

def query_database():
    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()

    cursor.execute("SELECT distance, co2, timestamp FROM sensor_data ORDER BY timestamp DESC")
    result = cursor.fetchall()

    connection.close()

    return result

def insert_data_into_database(distance, co2):
    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(id) FROM sensor_data")
    current_row_count = cursor.fetchone()[0]

    if current_row_count >= max_rows:
        rows_to_delete = current_row_count - max_rows + 1
        cursor.execute("DELETE FROM sensor_data WHERE id IN (SELECT id FROM sensor_data ORDER BY timestamp ASC LIMIT ?)", (rows_to_delete,))

    cursor.execute("INSERT INTO sensor_data (distance, co2) VALUES (?, ?)", (distance, co2))

    connection.commit()
    connection.close()

# Lytter til ultrasonic_topic og co2_topic 
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(ultrasonic_topic)
    client.subscribe(co2_topic)
    print(f"Subscribed to topics: {ultrasonic_topic}, {co2_topic}")

# Hvis der modtages noget på de topic den lytter på, så blive den værdi opdateret
def on_message(client, userdata, msg):
    global last_distance, last_co2
    payload = msg.payload.decode()
# Hvis afstanden er under 20 cm så bliver buzzeren aktiveret
    if msg.topic == ultrasonic_topic:
        last_distance = float(payload)
        print(f"Received Ultrasonic distance: {last_distance}")
        if last_distance < 20:
            pwm.ChangeDutyCycle(50)
            time.sleep(0.2)
            pwm.ChangeDutyCycle(0)
    elif msg.topic == co2_topic:
        last_co2 = float(payload)
        print(f"Received CO2 value: {last_co2}")
        insert_data_into_database(last_distance, last_co2)

    print(f"Received message on topic {msg.topic}: {payload}")
# oprettes forbindele til vores mqtt via username, password og porten
client = mqtt.Client()
client.username_pw_set(mqtt_user, mqtt_password)
client.on_connect = on_connect
client.on_message = on_message

client.connect(mqtt_server, mqtt_port, 60)
client.loop_start()

initialize_database()

@app.route('/get_database_data', methods=['GET'])
def get_database_data():
    data = query_database()
    return jsonify(data)

# starter flask på piens ip og på port 5001
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
