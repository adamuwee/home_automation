Goal
	v Develop and deploy an analytics platform that obtains data from the OpenHab instance, performs calculations, and publishes results back to OpenHab.

Examples
	1. Outside Temperature
		a. What is the high and low for the day? -> HighTempToday, LowTempToday
		b. What was the high and low for the month? HighTempMonth, LowTempMonth
		c. What was the average day time temperature from sunrise to sun set? AverageTempToday

	2. Water Consumption
		a. What is the current usage for the current day? WaterConsumedToday
		b. What was total consumption for a given day? Query last state of a day
		c. What is the current usage for the month? WaterConsumedMonth
		d. What was the total consumption for a month? Query last state of a month

Question:
It may be possible to only calculate running totals / averages for a given time period. For example, if I have a Python script calc'ing the month total and a power outage occurs unless the script is querying the DB the data would be lost.

If only the DB is queried, what is the latency? It would be nice to see near real-time water usage for example. Turn on the kitchen sink, see the water meter.

I like the idea of only using the SQL DB as the data source opposed to a hybrid or no-DB solution.

Hybrid => use the DB for historical and REST API for changes
No-DB => persist data in the analytics engine

The Hybrid approach would make it difficult to draw the line between live and recent

The No-DB approach would either need to create a duplicate DB or suffer from power outages.

By using the SQL DB only; the data is consistent, implementation is simpler and post-processing is available (could calculate daily and monthly values prior to analytics engine).

	Ø Prototype a Python script that tracks an OpenHab item through the OH DB server. Measure latency between input changes.

Design Requirements
	• Single Python Application
	• Hosted in Git
	• Re-deployable to other targets
	• No DB design; does not rely on local storage or persistence
	• Conf file: OH server, tokens, SQL server
		○ Conf file does not define OH Items, calcs, or any analytics detail; this shall be defined by the individual scripts
	• OO Design: Engine that runs multiple disparate analytics; extensible
		○ Analytics can be run with and without engine
		○ Engine restart automatically recognizes new modules
		○ User option of blocking fail or ignore fail (at start-up, during process)
	• Reads directly from DB and writes to OH; app shall not write data to the DB.
		○ SQL DB -> Analytics Engine -> OH
	• Add logging w/ 30 day rollover
		

Maria DB Python Connector
https://pypi.org/project/mariadb/

REST API
oh.AnalyticsREST.Joam2PJlMpGw8XTWa5JuVuSwuey7aS66S1SIQDcilavWbcJcSL5TlEEnu7SRj0FEqkkf1oTCGstZLKZKQ

-u '{API_TOKEN}:oh.AnalyticsREST.Joam2PJlMpGw8XTWa5JuVuSwuey7aS66S1SIQDcilavWbcJcSL5TlEEnu7SRj0FEqkkf1oTCGstZLKZKQ'

Get All Items Example
curl -X GET --header "Accept: application/json" "http://debian-openhab:8080/rest/items?recursive=false" --user 'oh.AnalyticsREST.Joam2PJlMpGw8XTWa5JuVuSwuey7aS66S1SIQDcilavWbcJcSL5TlEEnu7SRj0FEqkkf1oTCGstZLKZKQ:' 

Get Outside Temperature Example
curl -X GET --header "Accept: text/plain" "http://debian-openhab:8080/rest/items/WS_Temperature/state" --user 'oh.AnalyticsREST.Joam2PJlMpGw8XTWa5JuVuSwuey7aS66S1SIQDcilavWbcJcSL5TlEEnu7SRj0FEqkkf1oTCGstZLKZKQ:' 

Subscribe to Item Change
curl "http://debian-openhab:8080/rest/events?topics=openhab/items/AtticFanEntranceMotorCurrent/statechanged" --user 'oh.AnalyticsREST.Joam2PJlMpGw8XTWa5JuVuSwuey7aS66S1SIQDcilavWbcJcSL5TlEEnu7SRj0FEqkkf1oTCGstZLKZKQ:' 

Python Requests
https://docs.python-requests.org/en/master/user/advanced/#streaming-requests
import json
import requests

r = requests.get('https://httpbin.org/stream/20', stream=True)

for line in r.iter_lines():

    # filter out keep-alive new lines
    if line:
        decoded_line = line.decode('utf-8')
        print(json.loads(decoded_line))

Import requests
WH31_AtticEntrance_Temperature

Garage Door Monitor
-------------------

`garage_door.py` is a Linux service that reads the ioThinx 45MR-1600-0
`diStatusAll` Modbus input register, subscribes to the outside-wind MQTT topic,
and emits OTel log alerts to the configured OTLP endpoint. It exposes
`GET /health` with a JSON `status` of `running`, `degraded`, or `error`.

Copy `scripts/oh_analytics/.env.example` to a protected deployment location,
such as `/etc/garage-door/garage-door.env`, and set `MODBUS_HOST`. Confirm
`MODBUS_INPUT_REGISTER_ADDRESS` while observing a known door state: Moxa
documentation address `21504` may need a one-address adjustment because
Pymodbus reads protocol offsets. Channel 6 is ON when the door is closed and
OFF when it is open.

Install dependencies with `python3 -m pip install -r requirements.txt`. Copy
`garage-door.service` to `/etc/systemd/system/`, adjust its paths and service
account for the host, then run `systemctl daemon-reload` and
`systemctl enable --now garage-door`. Check the process with
`curl http://127.0.0.1:8088/health`.
