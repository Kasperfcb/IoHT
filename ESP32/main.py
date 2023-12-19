import urequests  # Giver os adgang til urequests biblioteket for at sende HTTP-anmodninger til IFTTT
import time # Giver os adgang at kunne sætte delay 
import machine # Giver os adgang til pins på vores esp32
import network # Giver os adgang til at kunne forbinde til wifi
from umqtt.simple import MQTTClient # Giver os adgang til at kunne komunikere med mqtt 
import neopixel # Giver os adgang til at kunne styre led'erne på vores neopixel

# Funktion til at læse afstand fra ultralydssensoren
def read_distance():
    trigger.value(1)
    time.sleep_us(10)
    trigger.value(0)

    while echo.value() == 0:
        pulse_start = time.ticks_us()

    while echo.value() == 1:
        pulse_end = time.ticks_us()

    pulse_duration = time.ticks_diff(pulse_end, pulse_start)
    return (pulse_duration * 0.0343) / 2

# Konfiguration af WiFi, MQTT og IFTTT for at sende SMS
ssid = "Testnet"
password = "123456789"
mqtt_server = "192.168.152.153"
mqtt_port = 1883
mqtt_user = "ioht"
mqtt_password = "kasper3600"
ultrasonic_topic = b"ultrasonic"
co2_topic = b"co2"
ifttt_event = "sensor"
ifttt_key = "wlY_6DPb1__JuVgv8l3Ch"

# Her oprette vi de farver vi skal bruge til vores neopixel
NEOPIXEL_COLOR_RED = (255, 0, 0)
NEOPIXEL_COLOR_GREEN = (0, 255, 0)
NEOPIXEL_COLOR_YELLOW = (255, 255, 0)
NEOPIXEL_COLOR_BLUE = (0, 0, 255)

# En funktion til at oprette forbindelse til WiFi
def connect_to_wifi():
    station = network.WLAN(network.STA_IF)
    if not station.isconnected():
        print("Forbinder til WiFi...")
        station.active(True)
        station.connect(ssid, password)
        while not station.isconnected():
            pass
    print("Forbundet til WiFi")
    print(station.ifconfig())

# En funktion til at sende en HTTP-anmodning til IFTTT som gør at vi kan modtage sms 
def send_ifttt_request():
    url = "http://maker.ifttt.com/trigger/{}/json/with/key/{}".format(ifttt_event, ifttt_key)
    response = urequests.post(url)
    print("IFTTT-anmodning sendt. Svarkode:", response.status_code)
    response.close()

# Funktion til at konvertere ADC-værdi fra MQ135 til CO2-koncentration i ppm
def adc_to_ppm(adc_value):
    adc_min, adc_max, co2_min, co2_max = 100, 3100, 10, 1000
    return int((adc_value - adc_min) * (co2_max - co2_min) / (adc_max - adc_min) + co2_min)

# Funktion til at kunne  indstille NeoPixel LED'en til en bestemt farve
def set_neopixel_color(color):
    np.fill(color)
    np.write()

while True:
    try:
        # Opret forbindelse til WiFi
        connect_to_wifi()

        # Opret MQTT forbindelse
        client = MQTTClient("sensor_client", mqtt_server, port=mqtt_port, user=mqtt_user, password=mqtt_password)

        client.connect()

        # Vælger hvilke pins vores ultralydssensor er på
        trigger_pin = 4
        echo_pin = 5
        trigger = machine.Pin(trigger_pin, machine.Pin.OUT)
        echo = machine.Pin(echo_pin, machine.Pin.IN)

        # Vælger hvilken pin vores mq135 er tilsluttet 
        co2_adc_pin = machine.ADC(machine.Pin(34))  

        # Vælger hvilke pins vores NeoPixel tilsluttet
        neopixel_pin = 22
        neopixel_leds = 12
        np = neopixel.NeoPixel(machine.Pin(neopixel_pin, machine.Pin.OUT), neopixel_leds)

        # Tidsvariabel til styring af at sørge for vores neopixel blive rød i 20 sekunder og at der ikke bliver sendt mqtt beskeder konstant 
        mqtt_send_interval = 1  # sekunder
        neopixel_red_duration = 20  # sekunder
        last_mqtt_send_time = 0
        last_neopixel_red_time = 0
        update_sent = False  # Variabel til at tjekke, om en opdatering er blevet sendt

        
        while True:
            try:
                # Tjekker om der er wifi forbindelse og hvis ikke så skiftes farven til blå på nepoixel 
                station = network.WLAN(network.STA_IF)
                if not station.isconnected():
                    set_neopixel_color(NEOPIXEL_COLOR_BLUE)  # Blå lys for tab af wifi forbindelse
                    print("Tabt forbindelse til WiFi. Genopretter forbindelse...")
                    connect_to_wifi()  # Forsøger automatisk at oprette forbindelse til wifi
                    break  

                distance = read_distance()
                print("Afstand:", distance)

                # Sender ultralydsdata til MQTT, hvis afstanden er under 20 cm
                if distance < 20 and not update_sent:
                    client.publish(ultrasonic_topic, str(distance))
                    update_sent = True

                    # Aktivere IFTTT-anmodning, hvs  aftsnadne er under 20cm
                    send_ifttt_request()

            except Exception as ultrasonic_error:
                print("Fejl ved læsning af ultralydssensor:", ultrasonic_error)

            try:
                co2_adc_value = co2_adc_pin.read()
                co2_concentration = adc_to_ppm(co2_adc_value)
                print("CO2 Koncentration:", co2_concentration, "ppm")

                # Sender  CO2 til MQTT
                client.publish(co2_topic, str(co2_concentration))

                # NeoPixel farvelogik baseret på vores betingelser
                current_time = time.time()

                if update_sent:
                    if (current_time - last_neopixel_red_time) < neopixel_red_duration:
                        set_neopixel_color(NEOPIXEL_COLOR_RED)  # Rød
                    else:
                        update_sent = False  # Nulstiler update_sent
                        set_neopixel_color(NEOPIXEL_COLOR_GREEN)  # Grøn

                elif distance > 20 and co2_concentration > 600:
                    set_neopixel_color(NEOPIXEL_COLOR_YELLOW)  # Gul
                    update_sent = False  # Nulstiler update_sent
                    last_neopixel_red_time = current_time  # Opdater tiden for gul betingelse

                elif distance >= 20 and co2_concentration < 600:
                    set_neopixel_color(NEOPIXEL_COLOR_GREEN)  # Grøn
                    last_neopixel_red_time = current_time  # Opdater tiden for grøn betingelse

                # Nulstiler update_sent efter 20 sekunder
                if update_sent and (current_time - last_neopixel_red_time) >= neopixel_red_duration:
                    update_sent = False
                    last_neopixel_red_time = current_time

                # Sender ultralydsdata til MQTT hvert 1. sekund
                if current_time - last_mqtt_send_time >= mqtt_send_interval:
                    if not update_sent:  # Send kun, hvis en opdatering ikke er blevet sendt for at undgå spam
                        client.publish(ultrasonic_topic, str(distance))
                    last_mqtt_send_time = current_time

                time.sleep(0.5)  

                # Kontroller vores mqtt forbindelse og lyser blå hvis forbindelsen til mqtt er mistet
                try:
                    client.ping()  # Dette vil kaste en undtagelse, hvis ikke forbundet
                except OSError:
                    set_neopixel_color(NEOPIXEL_COLOR_BLUE)  # Blå for tab af MQTT-forbindelse
                    print("Tabt forbindelse til MQTT. Genopretter forbindelse...")
                    client.connect()

            except Exception as main_loop_error:
                print("Fejl i hovedløkken:", main_loop_error)

    except Exception as main_loop_error:
        print("Hovedløkkefejl:", main_loop_error)
        time.sleep(5)  # venter 5 sekunder for at prøve at oprette forbindelse igen
