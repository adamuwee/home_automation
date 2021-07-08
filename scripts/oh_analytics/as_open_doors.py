import json
import requests
import re
import math
from datetime import datetime, date, time, timedelta
import logging
import sys
from os.path import exists
import time
import threading
import async_timer
import asyncio

# This analytics script monitors door states and sends an alarm if a door is open for an extended period of time.        
class as_open_door_monitor(threading.Thread): 
    # Globals
    _logger = None
    _analytics_conf = dict()
    _security_msg_uid = None
    _name = None
    _door_uid = None
    _door_timer_uid = None
    _security_msg_uid = None
    _timer = None
    _timer_start = None
    _door_is_open = False

    # Constants
    TIMER_INTERVAL_SECS = 1.0

    # Init 
    def __init__(self, logger, name, door_uid, door_timer_uid, security_msg_uid) -> None:
        threading.Thread.__init__(self)
        self._logger = logger
        self._name = name
        self._door_uid = door_uid
        self._door_timer_uid = door_timer_uid
        self._security_msg_uid = security_msg_uid
        self._init_analytics_conf()
        self._logger.info(f'{self._name}: door monitor object created')
        # Create Timer
        self._timer = async_timer.async_timer(self._logger, self.TIMER_INTERVAL_SECS, True, self._name, self, self._timer_event)

    def run(self):
        asyncio.run(self._sync_wait_on_door_change())

    # Set door state
    def _set_door_state(self, state):
        if state == 'OPEN':
            self._timer_start = datetime.now()
            self._door_is_open = True
        elif state == 'CLOSED':
            self._door_is_open = False       
            self._set_door_timer_value_oh(0)
        else:
            self._logger.warning(f'{self._name}: Attempted to set unknown door state: {state}')  
        self._logger.info(f"{self._name}:state:{self._door_is_open}")      

    def _timer_event(self, timer_name, context, timer):
        self._logger.info(f'{timer_name} event fired - Door State: {self._door_is_open}')
        if self._door_is_open == True:
            elapsed_time = datetime.now() - self._timer_start
            seconds = elapsed_time.seconds
            self._report_security_mgs_to_OH(f'{self._name} open for {seconds} secs')
            self._set_door_timer_value_oh(seconds)
    
    # Send a security message to OpenHab
    def _report_security_mgs_to_OH(self, message):
        url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/items/{self._security_msg_uid}/state"
        request = requests.put(url,  auth=(self._analytics_conf['oh_token'], ''), data=str(message), headers={ "Content-Type": "text/plain" })
        self._logger.info(f"{self._name}:security_analytics_msg:Request:put:{request.status_code}")
        self._logger.info(f"{self._name}:security_analytics_msg:{message}")
    
    # Set the open door timer value
    def _set_door_timer_value_oh(self, open_time_seconds):
        self._logger.info(f'Setting {self._name} open time to {open_time_seconds}')
        url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/items/{self._door_timer_uid}/state"
        request = requests.put(url,  auth=(self._analytics_conf['oh_token'], ''), data=str(open_time_seconds), headers={ "Content-Type": "text/plain" })
        self._logger.info(f"{self._name}:_set_door_timer_value_oh:Request:put:{request.status_code}")
        self._logger.info(f"{self._name}:_set_door_timer_value_oh:{open_time_seconds}")
                    
    # Open Hab Globals
    def _init_analytics_conf(self):
        # Locals
        json_file_name = 'oh_analytics_conf.json'

        # Create conf entries
        self._analytics_conf['oh_token'] = 'Insert_OH_Token_Here'
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
            self._logger.info(f'{self._name}: JSON conf loaded:\n{self._analytics_conf}')

        except:
            self._logger.error('Error occured while reading JSON conf file.')
            # Attempt to create default conf file
            file_exists = exists(json_file_name)
            if file_exists:
                self._logger.error(f'{self._name}: Cannot read conf file: {json_file_name}\rExiting.')
                sys.exit()
            else:
                self._logger.info('{self._name}: Attempting to create default JSON conf file.')
                json_object = json.dumps(self._analytics_conf, indent = 4)
                with open(json_file_name, "w") as outfile:
                    outfile.write(json_object)
                self._logger.info(f'{self._name}: Default conf file written: {json_file_name}\nPlease modify conf file for your system.\nExiting.')
                sys.exit()

    async def _sync_wait_on_door_change(self):
        # Get door state and update
        self._logger.info(f'{self._name}: Getting door state from OpenHab')
        openhab_url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/items/{self._door_uid}/state"
        request = requests.get(openhab_url, auth=(self._analytics_conf['oh_token'], ''))
        if request.encoding is None:
            request.encoding = 'utf-8'
        self._set_door_state(request.text)

        # Subscribe to OpenHab item state changes and process data
        self._logger.info(f'{self._name}: Waiting on status change from OpenHab')
        openhab_url = f"http://{self._analytics_conf['host']}:{self._analytics_conf['port']}/rest/events?topics=openhab/items/{self._door_uid}/statechanged"
        request = requests.get(openhab_url, stream=True, auth=(self._analytics_conf['oh_token'], ''))
        if request.encoding is None:
            request.encoding = 'utf-8'


        # Regex Parse
        data_header_pattern = re.compile(r'{"topic":.+"ItemStateChangedEvent"}$')

        for line in request.iter_lines(decode_unicode=True):
            # Search for 'data: ' string and convert to JSON
            matches = data_header_pattern.findall(line)
            self._logger.info(f'{line}')
            for match in matches:
                match = match.replace('\\','')
                match = match.replace('"{','{')
                match = match.replace('}"','}')
                json_data = json.loads(match)
                door_state = json_data["payload"]["value"]
                self._logger.info(f'Request text: {request.text}')
                self._set_door_state(door_state)

def main():
    # Configure Logger
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)
    # Debug File Log
    file = logging.FileHandler("debug_as_security.log")
    file.setLevel(logging.INFO)
    fileformat = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    file.setFormatter(fileformat)
    logger.addHandler(file)
    # Critical File Log
    cric_file = logging.FileHandler("critical_as_security.log")
    cric_file.setLevel(logging.CRITICAL)
    cric_file.setFormatter(fileformat)
    logger.addHandler(cric_file)
    # Create list of doors
    door_monitors = list()
    security_msg_uid = "security_analytics_msg"
    door_monitors.append(as_open_door_monitor(logger, 'Deck Door', 'DeckDoor', 'DeckDoorOpenTimer', security_msg_uid))
    door_monitors.append(as_open_door_monitor(logger, 'Garage Door', 'GarageDoor', 'GarageDoorOpenTimer', security_msg_uid))
    door_monitors.append(as_open_door_monitor(logger, 'Front Door', 'FrontDoor', 'FrontDoorOpenTimer', security_msg_uid))
    # Start door monitors
    for door_monitor in door_monitors:
        door_monitor.start()
    loop = asyncio.get_event_loop()
    loop.run_forever()

if __name__ == "__main__":
    main()