import smbus
import RPi.GPIO as GPIO
import time
import logging
import paho.mqtt.client as mqtt

# App Config
pwm_pin = 32
pwm_freq = 10000
top_sensor_i2c_addr = 0x44
bot_senosr_i2c_addr = 0x45

# App Constants
openhab_host = "debian-openhab"
mqtt_broker_port = 1883
temperature_digits = 0
humidity_digits = 0
wind_speed_digits = 0

# Fan Speed and Temp Settings (temp, duty cycle)
LOW_TEMP_RANGE = (74, 0)
MED_TEMP_RANGE = (85, 50)
HIGH_TEMP_RANGE = (85, 100)

# OpenHab Items / Points
top_temperature_uid = "ServerClosetTop_Temperature"
top_humidity_uid = "ServerClosetTop_Humidity"
bottom_temperature_uid = "ServerClosetBottom_Temperature"
bottom_humidity_uid = "ServerClosetBottom_Humidity"
fan_duty_cycle_uid = "ServerClosetFan_DutyCycle"
fan_1_tach = "ServerClosetFan_Tach1"
fan_2_tach = "ServerClosetFan_Tach2"
fan_3_tach = "ServerClosetFan_Tach3"

# MQTT Client
flag_connected = False
def on_connect(client, userdata, flags, rc):
	global flag_connected
	flag_connected = 1

def on_disconnect(client, userdata, rc):
	global flag_connected
	flag_connected = 0

client = mqtt.Client()

client.on_connect = on_connect
client.on_disconnect = on_disconnect
try:
	client.connect(openhab_host, mqtt_broker_port)
	client.loop_start()
except:
	print('MQTT client connect failure')
	flag_connected = False

# Read temperature and humidity from SHT31-D sensor on the I2C addr specified
def read_sht31_temp_humidity(addr):
        bus = smbus.SMBus(1)
        #addr = 0x44
        print(f"Reading address: {addr}")
        # SHT31 address, 0x44(68)
        bus.write_i2c_block_data(addr, 0x2C, [0x06])
        time.sleep(0.5)

        # SHT31 address, 0x44(68)
        # Read data back from 0x00(00), 6 bytes
        # Temp MSB, Temp LSB, Temp CRC, Humididty MSB, Humidity LSB, Humidity CRC
        data = bus.read_i2c_block_data(addr, 0x00, 6)

        # Convert the data
        temp = data[0] * 256 + data[1]
        cTemp = -45 + (175 * temp / 65535.0)
        fTemp = -49 + (315 * temp / 65535.0)
        humidity = 100 * (data[3] * 256 + data[4]) / 65535.0

        # Output data to screen
        print(f"SHT31 {addr} Temperature: {cTemp} C / {fTemp} F")
        print(f"SHT31 {addr} Relative Humidity: {humidity}%")
        bus.close()
        return (fTemp, humidity)

def init_fan_pwm():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(pwm_pin, GPIO.OUT)
    GPIO.output(pwm_pin, GPIO.LOW)
    global pwm
    pwm = GPIO.PWM(pwm_pin, pwm_freq)
    pwm.start(0)   

def set_fan_pwm(duty_cycle):
    # Invert DC
    inv_dc = 100 - duty_cycle
    pwm.ChangeDutyCycle(inv_dc)

def monitor_temp_update_fans():
    # Measure temperature
    (top_sensor_temp, top_sensor_humidity) = read_sht31_temp_humidity(top_sensor_i2c_addr)
    (bot_sensor_temp, bot_sensor_humidity) = read_sht31_temp_humidity(bot_senosr_i2c_addr)
    # Update Fan Speed - set to high, medium, or low
    (low_temp, low_dc) = LOW_TEMP_RANGE
    (med_temp, med_dc) = MED_TEMP_RANGE
    (high_temp, high_dc) = HIGH_TEMP_RANGE
    if top_sensor_temp <= low_temp:
        duty_cycle_set_point = low_dc
    elif top_sensor_temp > low_temp and top_sensor_temp <= med_temp:
        duty_cycle_set_point = med_dc
    else:
        duty_cycle_set_point = high_dc
    duty_cycle_set_point = 6.66 * top_sensor_temp - 500
    if duty_cycle_set_point < 0:
        duty_cycle_set_point = 0
    if duty_cycle_set_point > 100:
        duty_cycle_set_point = 100
    set_fan_pwm(duty_cycle_set_point)

    # Measure fan tach / rpm
    tach1 = 1
    tach2 = 2
    tach3 = 3
    
    # Measurement Dict
    measurements = dict()
    measurements[top_temperature_uid] = top_sensor_temp
    measurements[top_humidity_uid] = top_sensor_humidity
    measurements[bottom_temperature_uid] = bot_sensor_temp
    measurements[bottom_humidity_uid] = bot_sensor_humidity
    measurements[fan_duty_cycle_uid] = duty_cycle_set_point
    measurements[fan_1_tach] = tach1
    measurements[fan_2_tach] = tach2
    measurements[fan_3_tach] = tach3

    # Publish temperature and humidity values to OpenHab
    for uid, value in measurements.items():
        infot = client.publish(uid, round(value, 1), qos=1, retain=False)
        print(f"{uid}: {value}")
        infot.wait_for_publish()

def main():
    # Configure Logger
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)
    # Debug File Log
    file = logging.FileHandler("debug_sc_fan_controller.log")
    file.setLevel(logging.INFO)
    fileformat = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    file.setFormatter(fileformat)
    logger.addHandler(file)
    # Critical File Log
    cric_file = logging.FileHandler("critical_sc_fan_controller.log")
    cric_file.setLevel(logging.CRITICAL)
    cric_file.setFormatter(fileformat)
    logger.addHandler(cric_file)
    # Configure Fan PWM output
    init_fan_pwm()
    # Infinite loop of reporting temperature and setting fan speed based on temperature
    while True:
        # Check MQTT Client Connection
        if flag_connected == False:
            client.loop_stop()
            client.connect(openhab_host, mqtt_broker_port)
            client.loop_start()
            logger.info(f'MQTT Client Connected: {client}')

        monitor_temp_update_fans()
        time.sleep(1)

if __name__ == "__main__":
    main()