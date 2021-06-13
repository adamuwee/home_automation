import json
import requests

MaxTempToday = 123.456
#url = f"http://debian-openhab:8080/rest/events?topics=openhab/items/{item_uid}/statechanged"
token = "oh.AnalyticsREST.Joam2PJlMpGw8XTWa5JuVuSwuey7aS66S1SIQDcilavWbcJcSL5TlEEnu7SRj0FEqkkf1oTCGstZLKZKQ:"

daily_max_item_uid = "WS_Temperature_DailyMax"

#     "http://debian-openhab:8080/rest/items/WS_Temperature_DailyMax/state"
url = 'http://debian-openhab:8080/rest/items/{daily_max_item_uid}/state'
url = 'http://debian-openhab:8080/rest/items/WS_Temperature_DailyMax/state'
request = requests.put(url,  auth=(token, ''), \
                    data=str(MaxTempToday), \
                    headers={ "Content-Type": "text/plain" })
print(f"request.status_code:{request.status_code}")
print(f"request: {request}")
print(f"request.headers: {request.headers}")
print(f"MaxTempToday: {MaxTempToday}")
daily_min_item_uid = "WS_Temperature_DailyMin"