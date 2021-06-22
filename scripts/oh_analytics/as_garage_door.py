import json
import requests
import re
import math
from datetime import datetime, date, time
import logging
import sys
from os.path import exists
import time

# This analytics script covers several areas:
#   Garage Door - create a timer that expires at a specific time (e.g. 9:00pm) and checks garage door status

class as_security(): 
    # Globals
    _logger = None
    _analytics_conf = dict()
    # Garage Door
    _garage_door_down_sensor = "MoxaMR451600DI_ExternalGarageDoorDownSensor"
    _security_msg_uid = "security_analytics_msg"

    # Init 
    def __init__(self, logger) -> None:
        self._logger = logger
        self._logger.info('Garage Door Analytics object init')
        self._init_analytics_conf()
        pass
                
    # Open Hab Globals
    def _init_analytics_conf(self):
        # Locals
        json_file_name = 'oh_analytics_conf.json'

        # Create conf entries
        self._analytics_conf['oh_token'] = 'OH_Token'
        self._analytics_conf['host'] = 'debian-openhab'
        self._analytics_conf['port'] = '8080'

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
            self._openhab_url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/items/{self._garage_door_down_sensor}"
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

    def check_garage_door_status(self):
            self._logger.info(f'Checking garage door status change from Open Hab: {self._garage_door_down_sensor} ')
            # Subscribe to OpenHab item state changes and process data
            request = requests.get(self._openhab_url, auth=(self._analytics_conf['oh_token'], ''))

            if request.encoding is None:
                request.encoding = 'utf-8'

            
            text = request.text
            json_data = request.json()

            if json_data["state"] == "OPEN":
                self.report_to_OH("Garage Door is Open")

    def report_to_OH(self, message):
        self._logger.info("Reporting security message to Open Hab")
        url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/items/{self._security_msg_uid}/state"
        request = requests.put(url,  auth=(self._analytics_conf['oh_token'], ''), data=str(message), headers={ "Content-Type": "text/plain" })
        self._logger.info(f"security_analytics_msg:Request:put:{request.status_code}")
        self._logger.info(f"security_analytics_msg:{message}")

def main():
    # Configure Logger
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)
    # Debug File Log
    file = logging.FileHandler("debug_as_garage_door.log")
    file.setLevel(logging.INFO)
    fileformat = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    file.setFormatter(fileformat)
    logger.addHandler(file)
    # Critical File Log
    cric_file = logging.FileHandler("critical_as_garage_door.log")
    cric_file.setLevel(logging.CRITICAL)
    cric_file.setFormatter(fileformat)
    logger.addHandler(cric_file)
    # Create Temperature Analytics obj and wait for OH item status change
    ast = as_security(logger)
    ast.check_garage_door_status()   

if __name__ == "__main__":
    main()