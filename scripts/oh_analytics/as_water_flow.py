import json
import requests
import re
import math
from datetime import datetime, date, time
import logging
import sys
import oh_sql_client
from os.path import exists

class as_water_flow(): 

    # Globals
    _logger = None
    _oh_client = None
    _todays_absolute_value = math.inf
    _months_absolute_value = math.inf
    _todays_usage = 0
    _months_usage = 0
    _analytics_conf = dict()
    _openhab_url = None

    # Init
    def __init__(self, logger) -> None:
        self._logger = logger
        self._logger.info('Water Flow Analytics object init')
        self._init_analytics_conf()
        self._oh_client = oh_sql_client.oh_sql_client(None)
        self._get_first_counter_reading_for_day()
        self._get_first_counter_reading_for_month()
        self._get_last_value_and_init()
        pass
                
    # Open Hab Globals
    _water_flow_counter_uid = "MoxaMR451600DI_WaterMainsUsageGallons"
    _water_flow_daily_usage_uid = "WaterMainsDailyUsage"
    _water_flow_monthly_usage_uid = "WaterMainsMonthlyUsage"
    _LastTimeStamp = None

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
            self._openhab_url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/events?topics=openhab/items/{self._water_flow_counter_uid}/statechanged"
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

    # Get the last value and update daily and monthly on init
    def _get_last_value_and_init(self):
        last_value = self._oh_client.get_last_value(self._water_flow_counter_uid)[1]
        self.process_new_data(last_value)
        self.report_to_OH()

    # Get the first counter reading for the day
    def _get_first_counter_reading_for_day(self):
        # Get measurements for the day and assess min / max
        self._logger.info(f"Retrieving today's water flow counter value")
        first_value_today = self._oh_client.get_first_value_for_day(self._water_flow_counter_uid, datetime.now())
        # There may not be an updated value for the day if the counter has not changed.
        # In this case, just get the last value; this is okay as it means there's been no flow since the day change. 
        if len(first_value_today) == 0:
            last_value = self._oh_client.get_last_value(self._water_flow_counter_uid)
            self._todays_absolute_value = last_value[1]
        else:
            self._todays_absolute_value = next(iter(first_value_today.values()))
        self._logger.info(f"Today's starting value: {self._todays_absolute_value} gallons")

    def _get_first_counter_reading_for_month(self):
        # Get the first counter reading for the month
        self._logger.info(f"Retrieving this month's water flow counter value")
        first_value_month = self._oh_client.get_first_value_for_month(self._water_flow_counter_uid, datetime.now())
        # There may not be an updated value for the day if the counter has not changed.
        # In this case, just get the last value; this is okay as it means there's been no flow since the day change. 
        if len(first_value_month) == 0:
            last_value = self._oh_client.get_last_value(self._water_flow_counter_uid)
            self._months_absolute_value = last_value[1]
        else:
            self._months_absolute_value = next(iter(first_value_month.values()))
        self._logger.info(f"Month's starting value: {self._months_absolute_value} gallons")
    
    # Updates the daily and monthly water usage. Values updated based on flow counter change from OH3.
    def wait_for_item_status_change(self):
        self._logger.info(f'Waiting water flow counter change from Open Hab: {self._water_flow_counter_uid} ')
        # Subscribe to OpenHab item state changes and process data
        request = requests.get(self._openhab_url, stream=True, auth=(self._analytics_conf['oh_token'], ''))

        if request.encoding is None:
            request.encoding = 'utf-8'

        # Regex Parse
        data_header_pattern =re.compile(r'{"topic":.+"ItemStateChangedEvent"}$')

        for line in request.iter_lines(decode_unicode=True):
            # Search for 'data: ' string and convert to JSON
            matches = data_header_pattern.findall(line)
            # Iterate through matches and clean up for JSON parse
            for match in matches:
                match = match.replace('\\','')
                match = match.replace('"{','{')
                match = match.replace('}"','}')
                json_data = json.loads(match)
                value = float(json_data["payload"]["value"])
                self._logger.info(f'Water Flow Counter: {value} gallons')
                self.process_new_data(value)
                self.report_to_OH()

    # Update Daily and Monthly Usage after Counter Change
    def process_new_data(self, new_value):
        self._logger.info(f"Analyzing Data: {new_value}")
        if self._LastTimeStamp is None:
            self._LastTimeStamp  = datetime.now()

        # Check if min/max values should be reset
        now = datetime.now()
        # Reset Day
        if now.day != self._LastTimeStamp.day:
            self._logger.info(f'Reseting Day: {now} DNE {self._LastTimeStamp}')
            self._get_first_counter_reading_for_day()

        # Reset Month
        if now.month != self._LastTimeStamp.month:
            self._logger.info(f'Reseting Month: {now} DNE {self._LastTimeStamp}')
            self._get_first_counter_reading_for_month()
        
        # Update Last Reported Timestamp
        self._LastTimeStamp = now

        # Sanity check
        if new_value < self._todays_absolute_value:
            self._logger.warn(f'Negative daily water usage?! New Count: {now} less than todays start counter: {self._todays_absolute_value}')
        if new_value < self._months_absolute_value:
            self._logger.warn(f'Negative monthly water usage?! New Count: {now} less than months start counter: {self._months_absolute_value}')

        # Update Min/max values
        self._todays_usage = new_value - self._todays_absolute_value
        self._months_usage = new_value - self._months_absolute_value

    # Report daily and monthly water usage to OpenHab Server
    def report_to_OH(self):
        self._logger.info("Reporting daily and monthly water usage to OpenHab Server")
        # Example    "http://debian-openhab:8080/rest/items/WS_Temperature_DailyMax/state"
        # Daily Water Usage
        url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/items/{self._water_flow_daily_usage_uid}/state"
        request = requests.put(url,  auth=(self._analytics_conf['oh_token'], ''), data=str(self._todays_usage), headers={ "Content-Type": "text/plain" })
        self._logger.info(f"Todays Usage:{self._todays_usage}\tStatus Code: {request.status_code}")
        # Monthly Water Usage
        daily_min_item_uid = "WS_Temperature_DailyMin"
        url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/items/{self._water_flow_monthly_usage_uid}/state"
        request = requests.put(url,  auth=(self._analytics_conf['oh_token'], ''), data=str(self._months_usage), headers={ "Content-Type": "text/plain" })
        self._logger.info(f"Todays Usage:{self._months_usage}\tStatus Code: {request.status_code}")

def main():
    # Configure Logger
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)
    # Debug File Log
    file = logging.FileHandler("debug_as_water_flow.log")
    file.setLevel(logging.INFO)
    fileformat = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    file.setFormatter(fileformat)
    logger.addHandler(file)
    # Critical File Log
    cric_file = logging.FileHandler("critical_as_water_flow.log")
    cric_file.setLevel(logging.CRITICAL)
    cric_file.setFormatter(fileformat)
    logger.addHandler(cric_file)
    # Create Temperature Analytics obj and wait for OH item status change
    ast = as_water_flow(logger)
    ast.wait_for_item_status_change()

if __name__ == "__main__":
    main()
