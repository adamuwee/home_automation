import subprocess
import json
from subprocess import Popen, PIPE
import paho.mqtt.client as mqtt
import time
import logging
import sys, traceback

# App Constants
openhab_host = "debian-openhab"
mqtt_broker_port = 1883
temperature_digits = 0
humidity_digits = 0
wind_speed_digits = 0
enable_dual_band_mode = False

# Configure Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
logger = logging.getLogger(__name__)
# Debug File Log
file = logging.FileHandler("debug_acurite.log")
file.setLevel(logging.INFO)
fileformat = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
file.setFormatter(fileformat)
logger.addHandler(file)

# RTL 433 shell command; set to 915 MHz and json output
# Hops every 25 seconds between 433.92 and 915 MHz for Acurite Weather Stations and Ambient Weather WH31
#cmd = 'rtl_433 -F json -f 915000000'
#cmd = 'rtl_433 -F json -f 915000000 -f 433920000 -H 25 -R 40 -R 113'
cmd = 'rtl_433 -d 1 -F json -f 433920000'

if enable_dual_band_mode:
	logger.info('Dual mode enabled')
	cmd = 'rtl_433 -d 1 -F json -f 915000000 -f 433920000 -H 25 -R 40 -R 113'

logger.info('Using rtL_433 command : ' + cmd)

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
	logger.warning('MQTT client connect failure')
	flag_connected = False

now = time.time()
report_window_sec = 5
AR_WeatherStation_sample_ts = {
	49: now,
	56: now,
}

def Parse_AcuriteWeatherStation(dd):
	# Acurite Weather Station JSON Data Sample:
	#
	# {"time" : "2021-03-11 10:30:38", "model" : "Acurite-5n1", "message_type" : 56, "id" : 719, "channel" : "C", "sequence_num" : 0, "battery_ok" : 1, "wind_avg_km_h" : 3.483, "temperature_F" : 67.300, "humidity" : 53, "mic" : "CHECKSUM"}
	# {"time" : "2021-03-11 10:30:38", "model" : "Acurite-5n1", "message_type" : 56, "id" : 719, "channel" : "C", "sequence_num" : 1, "battery_ok" : 1, "wind_avg_km_h" : 3.483, "temperature_F" : 67.300, "humidity" : 53, "mic" : "CHECKSUM"}
	# {"time" : "2021-03-11 10:30:38", "model" : "Acurite-5n1", "message_type" : 56, "id" : 719, "channel" : "C", "sequence_num" : 2, "battery_ok" : 1, "wind_avg_km_h" : 3.483, "temperature_F" : 67.300, "humidity" : 53, "mic" : "CHECKSUM"}
	# {"time" : "2021-03-11 10:30:56", "model" : "Acurite-5n1", "message_type" : 49, "id" : 719, "channel" : "C", "sequence_num" : 0, "battery_ok" : 1, "wind_avg_km_h" : 1.828, "wind_dir_deg" : 112.500, "rain_in" : 60.510, "mic" : "CHECKSUM"}
	# {"time" : "2021-03-11 10:31:14", "model" : "Acurite-5n1", "message_type" : 56, "id" : 719, "channel" : "C", "sequence_num" : 0, "battery_ok" : 1, "wind_avg_km_h" : 3.483, "temperature_F" : 67.300, "humidity" : 53, "mic" : "CHECKSUM"}
	# {"time" : "2021-03-11 10:31:14", "model" : "Acurite-5n1", "message_type" : 56, "id" : 719, "channel" : "C", "sequence_num" : 1, "battery_ok" : 1, "wind_avg_km_h" : 3.483, "temperature_F" : 67.300, "humidity" : 53, "mic" : "CHECKSUM"}
	# {"time" : "2021-03-11 10:31:14", "model" : "Acurite-5n1", "message_type" : 56, "id" : 719, "channel" : "C", "sequence_num" : 2, "battery_ok" : 1, "wind_avg_km_h" : 3.483, "temperature_F" : 67.300, "humidity" : 53, "mic" : "CHECKSUM"}
	logger.info('Acurite Parser Started!')

	# Check last timestamp and filter
	last_report = AR_WeatherStation_sample_ts[dd["message_type"]]
	report_delta = time.time() - last_report

	if report_delta < report_window_sec:
		return
	
	if 'message_type' not in dd:
		logger.warning('message_type key not found in Acurite Weather data')
		return

	if dd["message_type"] == 56:
		topic_channel = "acurite_ws/"
		# Temperature
		temperature_F = round(float(dd["temperature_F"]), temperature_digits)
		infot = client.publish(topic_channel + "temperature", round(temperature_F,1), qos=1, retain=False)
		logger.info(topic_channel + "temperature/" + str(temperature_F))
		infot.wait_for_publish()

		# Humidity
		humidity = round(float(dd["humidity"]), humidity_digits)
		infot = client.publish(topic_channel + "humidity", round(humidity,1), qos=1, retain=False)
		logger.info(topic_channel + "humidity/" + str(humidity))
		infot.wait_for_publish()

		# Wind
		wind = dd["wind_avg_km_h"]
		wind = round(wind * 0.6213712, wind_speed_digits)	# Convert kmh to mph
		infot = client.publish(topic_channel + 'wind_avg', wind, qos=1, retain=False)
		logger.info(topic_channel + "wind_avg/" + str(wind))
		infot.wait_for_publish()
		
		# Update last report time
		AR_WeatherStation_sample_ts[dd["message_type"]] = time.time()

	if dd["message_type"] == 49:
		topic_channel = "acurite_ws/"
		# Wind
		wind = dd["wind_avg_km_h"]
		wind = round(wind * 0.6213712, wind_speed_digits)	# Convert kmh to mph
		infot = client.publish(topic_channel + "wind_avg", wind, qos=1, retain=False)
		logger.info(topic_channel + "wind_avg/" + str(wind))
		infot.wait_for_publish()

		# Wind Direction (deg)
		wind_dir = dd["wind_dir_deg"]
		infot = client.publish(topic_channel + "wind_dir", wind_dir, qos=1, retain=False)
		logger.info(topic_channel + "wind_dir/" + str(wind_dir))
		infot.wait_for_publish()

		# Rain (inches)
		rain_in = dd["rain_in"]
		infot = client.publish(topic_channel + "rain_total", rain_in, qos=1, retain=False)
		logger.info(topic_channel + "rain_total/" + str(rain_in))
		infot.wait_for_publish()
		
		# Update last report time
		AR_WeatherStation_sample_ts[dd["message_type"]] = time.time()

# Sample Timestamp Dictionary - prevent duplicate MQTT messages as the WH31 transmits redundant data payloads
now = time.time()
report_window_sec = 5
AW_WH31_sample_ts = {
	1: now,
	2: now,
	3: now,
	4: now,
	5: now,
	6: now,
	7: now,
	8: now,
}

# Parsing Functions per Model
def Parse_AmbientWeatherWH31(dd):
	# Ambient WH31 JSON Data Sample:
	#
	# 	{'time': '2021-01-05 23:10:28', 
	#	 'model': 'AmbientWeather-WH31E', 
	#	 'id': 103, 
	#	 'channel': 8, 
	#	 'battery_ok': 1, 
	#	 'temperature_C': 6.5, 
	#	 'humidity': 65, 
	#	 'data': 'a000000000', 
	#	 'mic': 'CRC'}

	# Check if the channel recently transmitted
	logger.info('Ambient Weather Parser Started!')

	if 'channel' not in dd:
		logger.warning('channel key not found in WH31 data')
		return

	last_report = AW_WH31_sample_ts[dd["channel"]]
	report_delta = time.time() - last_report
	if report_delta > report_window_sec: 
		topic_channel = "amiweather/" + str(dd["channel"]) + "/"
		# Temperature
		temperature_F = round(float(dd["temperature_C"]) * 1.8 + 32.0, temperature_digits)
		infot = client.publish(topic_channel + "temperature", round(temperature_F,1), qos=1, retain=False)
		logger.info(topic_channel + "temperature/" + str(temperature_F))
		infot.wait_for_publish()
		# Humidity
		humidity = round(float(dd["humidity"]), humidity_digits)
		infot = client.publish(topic_channel + "humidity", round(humidity,1), qos=1, retain=False)
		logger.info(topic_channel + "humidity/" + str(humidity))
		infot.wait_for_publish()
		# Battery
		battery = dd["battery_ok"]
		infot = client.publish(topic_channel + "battery", battery, qos=1, retain=False)
		logger.info(topic_channel + "battery/" + str(battery))
		infot.wait_for_publish()
		# Update last report time
		AW_WH31_sample_ts[dd["channel"]] = time.time()

# Process Open of rtl_433 SDR
with Popen(cmd, shell=True, stdout=PIPE, bufsize=1, universal_newlines=True) as p:
	try:
		for line in p.stdout:
			# Check MQTT Client Connection
			if flag_connected == False:
				client.loop_stop()
				client.connect(openhab_host, mqtt_broker_port)
				client.loop_start()
				logger.info(f'MQTT Client Connected: {client}')

			# Convert json output to dictionary
			data_dict = json.loads(line)

			# Print / debug
			logger.info(data_dict)
			key = 'model'
			if key in data_dict:
				# Check Model Type
				if data_dict[key] == 'Acurite-5n1':
					Parse_AcuriteWeatherStation(data_dict)
				elif data_dict[key] == 'AmbientWeather-WH31E':
					Parse_AmbientWeatherWH31(data_dict)
				else:
					logger.warning('unknown model type parsed: ' + line)

	except KeyboardInterrupt:
		logger.warn("User exit")
		p.terminate()

logger.error('Unexpected exit: ' + str(p))
logger.error('Traceback: ' + str(traceback.print_exc()))
p.terminate()
