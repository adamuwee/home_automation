import json
import requests
import re
import math
from datetime import datetime, date, time
import logging
import sys
import oh_sql_client
from os.path import exists

# This analytics script covers several areas:
#   Garage Door
#   Open door for extended period of time
#   Door or Motion detected while away

class as_security(): 
    # Globals
    _logger = None
    _analytics_conf = dict()
    _garage_door_down_sensor = "MoxaMR451600DI_ExternalGarageDoorDownSensor"
    _oh_client = None

    # Init 
    def __init__(self, logger) -> None:
        self._logger = logger
        self._logger.info('Security Analytics object init')
        self._oh_client = oh_sql_client.oh_sql_client(None)
        self._init_analytics_conf()
        self._backlog_data()
        pass
                
    # Open Hab Globals
    def _init_analytics_conf(self):
        # Locals
        json_file_name = 'oh_analytics_conf.json'

        # Create conf entries
        self._analytics_conf['oh_token'] = 'SQL User Name'
        self._analytics_conf['host'] = 'OH SQL Host Name'
        self._analytics_conf['port'] = '3306'

        # Read json conf
        try:
            with open(json_file_name, 'r') as json_conf_file:
                json_data = json_conf_file.read()
                json_conf_file.close()
            json_obj = json.loads(json_data)
            self._analytics_conf['oh_token'] = json_obj['oh_token']
            self._analytics_conf['host'] = json_obj['host']
            self._analytics_conf['port'] = json_obj['port']
            self._logger.info(f'JSON conf loaded:\n{self._analytics_conf}')
            self._openhab_url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/events?topics=openhab/items/{self._garage_door_down_sensor}/statechanged"
        except:
            self._logger.error('Error occured while reading JSON conf file.')
            # Attempt to create default conf file
            file_exists = exists(json_file_name)
            if file_exists:
                self._logger.error(f'Cannot read conf file: {json_file_name}\rExiting.')
                sys.exit()
            else:
                self._logger.info('Attempting to create default JSON conf file.')
                json_object = json.dumps(self._analytics_conf, indent = 4)
                with open(json_file_name, "w") as outfile:
                    outfile.write(json_object)
                self._logger.info(f'Default conf file written: {json_file_name}\nPlease modify conf file for your system.\nExiting.')
                sys.exit()

    def wait_for_item_status_change(self):
            self._logger.info(f'Waiting garage door status change from Open Hab: {self._item_uid} ')
            # Subscribe to OpenHab item state changes and process data
            request = requests.get(self._openhab_url, stream=True, auth=(self._analytics_conf['oh_token'], ''))

            if request.encoding is None:
                request.encoding = 'utf-8'

            # Regex Parse
            data_header_pattern =re.compile(r'{"topic":.+"ItemStateChangedEvent"}$')

            for line in request.iter_lines(decode_unicode=True):
                # Search for 'data: ' string and convert to JSON
                matches = data_header_pattern.findall(line)
                
                for match in matches:
                    match = match.replace('\\','')
                    match = match.replace('"{','{')
                    match = match.replace('}"','}')
                    json_data = json.loads(match)
                    value = float(json_data["payload"]["value"])
                    self.analyze_data(value)
                    self.report_to_OH()
                    self.logger.info(f'Weather Station Temperture: {value} deg F')

    def analyze_data(self, new_value):
        self._logger.info(f"Analyzing Data: {new_value}")
        if self._last_timestamp is None:
            self._last_timestamp  = datetime.now()

        # Check if min/max values should be reset
        now = datetime.now()
        # Reset Day
        if now.day != self._last_timestamp.day:
            self.MaxTempToday = -math.inf
            self.MinTempToday = math.inf
            self._logger.info(f'Reseting Day: {now} DNE {self._last_timestamp}')
        # Reset Month
        if now.month != self._last_timestamp.month:
            self.MaxTempMonth = -math.inf
            self.MinTempMonth = math.inf
            self._logger.info(f'Reseting Month: {now} DNE {self._last_timestamp}')
        self._last_timestamp = now
        # Update Min/max values
        self.MaxTempToday = max(self.MaxTempToday, new_value)
        self.MinTempToday = min(self.MinTempToday, new_value)
        self.MaxTempMonth = max(self.MaxTempMonth, new_value)
        self.MinTempMonth = min(self.MinTempMonth, new_value)

    def report_to_OH(self):
        self._logger.info("Reporting to Open Hab")
        daily_max_item_uid = "WS_Temperature_DailyMax"
        #     "http://debian-openhab:8080/rest/items/WS_Temperature_DailyMax/state"
        url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/items/{daily_max_item_uid}/state"
        request = requests.put(url,  auth=(self._analytics_conf['oh_token'], ''), data=str(self.MaxTempToday), headers={ "Content-Type": "text/plain" })
        self._logger.info(f"MaxTempToday:Request:put:{request.status_code}")
        self._logger.info(f"MaxTempToday:{self.MaxTempToday}")
        daily_min_item_uid = "WS_Temperature_DailyMin"
        url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/items/{daily_min_item_uid}/state"
        request = requests.put(url,  auth=(self._analytics_conf['oh_token'], ''), data=str(self.MinTempToday), headers={ "Content-Type": "text/plain" })
        self._logger.info(f"MinTempToday:Request:put:{request.status_code}")
        self._logger.info(f"MinTempToday:{self.MinTempToday}")

def main():
    # Configure Logger
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)
    # Debug File Log
    file = logging.FileHandler("debug_as_temperature.log")
    file.setLevel(logging.INFO)
    fileformat = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    file.setFormatter(fileformat)
    logger.addHandler(file)
    # Critical File Log
    cric_file = logging.FileHandler("critical_as_temperature.log")
    cric_file.setLevel(logging.CRITICAL)
    cric_file.setFormatter(fileformat)
    logger.addHandler(cric_file)
    # Create Temperature Analytics obj and wait for OH item status change
    ast = as_security(logger)
    ast.wait_for_item_status_change()

if __name__ == "__main__":
    main()