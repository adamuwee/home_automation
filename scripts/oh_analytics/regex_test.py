import json
import requests
import re

# Regex Parse
line = 'data: {"topic":"openhab/items/AtticFanEntranceMotorCurrent/statechanged","payload":"{\"type\":\"Decimal\",\"value\":\"3.03\",\"oldType\":\"Decimal\",\"oldValue\":\"3.038\"}","type":"ItemStateChangedEvent"}'
#line = 'data: {"topic":"openhab/items/AtticFanEntranceMotorCurrent/statechanged","payload":"{"type":"Decimal","value":"2.995","oldType":"Decimal","oldValue":"2.991"}","type":"ItemStateChangedEvent"}'
data_header_pattern =re.compile(r'{"topic":.+')
print(line)
#matches = data_header_pattern.finditer(line)
matches = data_header_pattern.findall(line)

for match in matches:
    match = match.replace('"{','{')
    match = match.replace('}"','}')
    print(match)
    print(json.loads(match))

   #{"topic":"openhab/items/AtticFanEntranceMotorCurrent/statechanged","payload":"{"type":"Decimal","value":"3.03","oldType":"Decimal","oldValue":"3.038"}","type":"ItemStateChangedEvent"}