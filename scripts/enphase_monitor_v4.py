import http.client
import base64
import json
import os
from os.path import exists
from datetime import datetime
import paho.mqtt.client as mqtt
import time

# Watt Plan Access:
#  System Details
#  Site level Production Monitoring
#  Site level Consumption Monitoring

class EnphaseV4:

    # App Constants
    _MAX_REFRESH_ATTEMPS = 5

    # Private Class Members
    _config = None
    _debug_print_enabled = True
    _refresh_token_count = 0

    def __init__(self, config_path = ""):
        self._config = _config = EnphaseV4Config(config_path)

    def get_access_tokens(self) -> dict:
        conn = http.client.HTTPSConnection(self._config.api_url)
        payload = ''
        encoder_input = f'{self._config.client_id}:{self._config.client_secret}'
        input_bytes = encoder_input.encode("ascii")
        b64_encoded = base64.b64encode(input_bytes)
        self._debug_print("B64 Encoding: " + str(b64_encoded))
        decoded = b64_encoded.decode('utf-8')
        headers = {'Authorization': f'Basic {decoded}'}
        self._debug_print("Headers: " + str(headers))
        conn.request("POST", f"/oauth/token?grant_type=authorization_code&redirect_uri=https://api.enphaseenergy.com/oauth/redirect_uri&code={self._config.passcode}", payload, headers)
        res = conn.getresponse()
        data = res.read()
        self._debug_print(data.decode("utf-8"))
        if (res.status == 200):
            # Access Token received; update tokens
            self._refresh_token_count = 0
            json_data = json.loads(data)
            self._config.access_token = json_data["access_token"]
            self._config.refresh_token = json_data["refresh_token"]
            self._config.save_to_disk()
            return json_data
        else:
            # Attempt to refresh the token
            self._refresh_token_count = self._refresh_token_count + 1
            refresh_result = self._refresh_token(True)
            return refresh_result
        
    def _refresh_token(self, update_config = True) -> dict:
        conn = http.client.HTTPSConnection(self._config.api_url)
        payload = ''
        encoder_input = f'{self._config.client_id}:{self._config.client_secret}'
        input_bytes = encoder_input.encode("ascii")
        b64_encoded = base64.b64encode(input_bytes)
        self._debug_print("B64 Encoding: " + str(b64_encoded))
        decoded = b64_encoded.decode('utf-8')
        headers = {'Authorization': f'Basic {decoded}'}
        self._debug_print("Headers: " + str(headers))
        conn.request("POST", f"/oauth/token?grant_type=refresh_token&refresh_token={self._config.refresh_token}", payload, headers)
        res = conn.getresponse()
        if (res.status == 200):
            data = res.read()
            json_data = json.loads(data)
            if (update_config):
                self._config.access_token = json_data["access_token"]
                self._config.refresh_token = json_data["refresh_token"]
                self._config.save_to_disk()
            return json.loads(data)
        else:
            self._debug_print("ERROR" + str(res.read()))
            return None

    def _get_authorization_token(self) -> dict:
        encoder_input = f'{self._config.client_id}:{self._config.client_secret}'
        input_bytes = encoder_input.encode("ascii")
        b64_encoded = base64.b64encode(input_bytes)
        self._debug_print("B64 Encoding: " + str(b64_encoded))
        decoded = b64_encoded.decode('utf-8')
        header = {'Authorization': f'Basic {decoded}'}
        return header

    def get_system_summary(self) -> dict:
        return self._enphase_api_request("summary")

    def get_system_devices(self) -> dict:
        return self._enphase_api_request("devices")

    def get_battery_status(self) -> dict:
        return self._enphase_api_request("telemetry/battery")
    
    def get_battery_charge(self) -> int:
        battery = enphase.get_battery_status()
        if (battery != None):
            bat_charge_str = battery["last_reported_aggregate_soc"]
            bat_charge_str = bat_charge_str.replace('%','')
            return int (bat_charge_str)
        else:
            return None
    
    def _enphase_api_request(self, path) -> dict:
        conn = http.client.HTTPSConnection(self._config.api_url)
        payload = ''
        headers = {'Authorization': f"Bearer {self._config.access_token}"}
        conn.request("GET", f"/api/v4/systems/{self._config.system_id}/{path}?key={self._config.api_key}", payload, headers)
        res = conn.getresponse()
        if (res.status == 200):
            data = res.read()
            return json.loads(data)
        elif (res.status == 401):
            # Attempt to refresh the access token
            self._refresh_token_count = self._refresh_token_count + 1
            if (self._refresh_token_count > self._MAX_REFRESH_ATTEMPS):
                self._debug_print(f"FATAL ERROR: Max number of refresh attempts (count: {self._refresh_token_count}) reached. Exiting program")
                exit()
            else:
                self._refresh_token(True)
                return self._enphase_api_request(path) # recursive call
        else:
            self._debug_print("ERROR" + str(res.read()))
            return None  

    def _debug_print(self, debug_msg) -> None:
        if (self._debug_print_enabled):
            current_dateTime = datetime.now()
            print(f"EnphaseV4 [{current_dateTime}]\t{debug_msg}")

class EnphaseV4Config:



    def __init__(self, config_file_path) -> None:
        # Private Class Members
        self.config_file_path = config_file_path
        self.access_token = ""
        self.refresh_token = ""
        self.api_key = ""
        self.system_id = ""
        self.client_id = ""
        self.client_secret = ""
        self.passcode = ""
        self.api_url = ""
        self.report_time_minuntes = 0

        # Load config from JSON (or create default if it does not exist)
        if os.path.exists(self.config_file_path):
            self.update_from_json(self.config_file_path)
        else:
            # create default file
            json_str = self.to_json()  
            with open( self.config_file_path , "w" ) as write:
                write.write(json_str)
            #self._debug_print(f"FATAL ERROR: Cannot file config file: [{config_file_path}]. Exiting program")
            #exit()
    
    def save_to_disk(self):
        json_str = self.to_json()
        with open( self.config_file_path , "w" ) as write:
            write.write(json_str) 

    def to_json(self) -> str:
        d = dict()
        # top-level params
        for key, val in self.__dict__.items():
            d[key] = val
        return json.dumps(d)

    def update_from_json(self, file_path):
        # Read json file
        with open(file_path, 'r') as openfile:
            json_dict = json.load(openfile)      
            for key, val in json_dict.items():
                if key in self.__dict__.keys():
                    self.__dict__[key] = val
                else:
                    raise Exception("Unknown key found while loading board config: {file_path}. Key = {key}\tValue = {val}")

class OHClient:
    # App Constants
    openhab_host = "debian-openhab"
    mqtt_broker_port = 1883

    # Private Class Members
    client = None
    flag_connected = 0

    # MQTT Client
    flag_connected = False
    def on_connect(self, client, userdata, flags, rc):
        self.flag_connected = 1

    def on_disconnect(self, client, userdata, rc):
        self.flag_connected = 0

    def __init__(self) -> None:
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        try:
            self.client.connect(self.openhab_host, self.mqtt_broker_port)
            self.client.loop_start()
        except:
            print('MQTT client connect failure')
            self.flag_connected = False
    
    def publish_value(self, item_name, item_value):
        infot = self.client.publish(item_name, item_value, qos=1, retain=False)
        infot.wait_for_publish()

if __name__=="__main__":

    # Create Enphase and OpenHab Client object
    enphase = EnphaseV4("enphasev4_config.json")
    client = OHClient()
    # Loop forever
    delay_minutes = 5
    while True:
        # Get Battery Charge
        print("---------------------------------------------------------------------------------------")
        charge = enphase.get_battery_charge()
        enphase._debug_print("Battery charge = " + str(charge) + "%")
        # Post to OpenHab
        client.publish_value("BatteryCharge", charge)
        # Pause
        report_time_seconds = enphase._config.report_time_minuntes * 60
        enphase._debug_print(f"Sleeping for {enphase._config.report_time_minuntes} minutes.")
        time.sleep(report_time_seconds)