import http.client
import base64
import json
from os.path import exists
from datetime import datetime
import paho.mqtt.client as mqtt

# Watt Plan Access:
#  System Details
#  Site level Production Monitoring
#  Site level Consumption Monitoring

class EnphaseV4:

    # Private Class Members
    _config = None
    _debug_print_enabled = True

    def __init__(self, config_path = ""):
        self._config = _config = EnphaseV4Config(config_path)

    def get_access_tokens(self) -> dict:
        conn = http.client.HTTPSConnection(self._config.api_url)
        payload = ''
        encoder_input = f'{self._config.client_id}:{self._config.client_secret}'
        input_bytes = encoder_input.encode("ascii")
        b64_encoded = base64.b64encode(input_bytes)
        self._debug_print("B64 Encoding: " + str(b64_encoded))
        #headers = {'Authorization': 'Basic NWU2YzIxZTg2NzUxY2NhMjNjODRiNDk2NzEyNWNhOWM6NzgxYTJjMDAyZjZkNjU3ZTZjMjFlYjIwZmZjM2JiMWU='}
        decoded = b64_encoded.decode('utf-8')
        headers = {'Authorization': f'Basic {decoded}'}
        self._debug_print("Headers: " + str(headers))
        conn.request("POST", f"/oauth/token?grant_type=authorization_code&redirect_uri=https://api.enphaseenergy.com/oauth/redirect_uri&code={self._config.passcode}", payload, headers)
        res = conn.getresponse()
        data = res.read()
        self._debug_print(data.decode("utf-8"))
        return json.loads(data)
    
    def _refresh_token(self, update_config = True) -> dict:
        ## Not Working as of 1/14/2023. Receiving a method not allowed (405) from server.
        conn = http.client.HTTPSConnection(self._config.api_url)
        payload = ''
        header = self._get_authorization_token()
        conn.request("GET", f"/oauth/token?grant_type=refresh_token&refresh_token={self._config.refresh_token}", payload, header)
        res = conn.getresponse()
        if (res.status == 200):
            data = res.read()
            json_data = json.loads(data)
            if (update_config):
                self._config.access_token = json_data["access_token"]
                self._config.refresh_token = json_data["refresh_token"]
            return json.loads(data)
        else:
            self._debug_print("ERROR" + str(res.read()))
            return None

    def _get_authorization_token(self) -> dict:
        encoder_input = f'{self._config.client_id}:{self._config.client_secret}'
        input_bytes = encoder_input.encode("ascii")
        b64_encoded = base64.b64encode(input_bytes)
        self._debug_print("B64 Encoding: " + str(b64_encoded))
        #header = {'Authorization': 'Basic NWU2YzIxZTg2NzUxY2NhMjNjODRiNDk2NzEyNWNhOWM6NzgxYTJjMDAyZjZkNjU3ZTZjMjFlYjIwZmZjM2JiMWU='}
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
        else:
            self._debug_print("ERROR" + str(res.read()))
            return None 

    def _enphase_config_api_request(self, path) -> dict:
        conn = http.client.HTTPSConnection(self._config.api_url)
        payload = ''
        headers = {'Authorization': f"Bearer {self._config.access_token}"}
        conn.request("GET", f"/api/v4/systems/config/{self._config.system_id}/{path}?key={self._config.api_key}", payload, headers)
        res = conn.getresponse()
        if (res.status == 200):
            data = res.read()
            return json.loads(data)
        else:
            self._debug_print("ERROR" + str(res.read()))
            return None     

    def _debug_print(self, debug_msg) -> None:
        if (self._debug_print_enabled):
            current_dateTime = datetime.now()
            print(f"EnphaseV4 [{current_dateTime}]\t{debug_msg}")

class EnphaseV4Config:

    access_token = "eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOlsib2F1dGgyLXJlc291cmNlIl0sImFwcF90eXBlIjoic3lzdGVtIiwiaXNfaW50ZXJuYWxfYXBwIjpmYWxzZSwidXNlcl9uYW1lIjoiYWRhbXV3ZWVAZ21haWwuY29tIiwic2NvcGUiOlsicmVhZCIsIndyaXRlIl0sImVubF9jaWQiOiIiLCJlbmxfcGFzc3dvcmRfbGFzdF9jaGFuZ2VkIjoiMTU5MTYzMDMwOSIsImV4cCI6MTY3Mzc5MzUzMCwiZW5sX3VpZCI6IjE5NjUxMzMiLCJhdXRob3JpdGllcyI6WyJST0xFX1VTRVIiXSwianRpIjoiMmQzNGFiZmItN2U5Ni00NzYxLWE2ODQtM2Y5OTNhNTU1YWY0IiwiY2xpZW50X2lkIjoiNWU2YzIxZTg2NzUxY2NhMjNjODRiNDk2NzEyNWNhOWMifQ.htoChd0e4dlZT3wz7krFoBDdywujK1u7aBTri0LBnT7AKi5B5O91RBpdiyNG5bxIZzwSMU54zbmdpY7ouy5oelv4_MzZY-H3E3NG7BKRVWHrujRF6X8J2BQ0HcaZrJ0BcPtYbbTPMgk1gxoxLZU0FkMfdz766vONYOsFB9RqXMs"
    refresh_token = "eyJhbGciOiJSUzI1NiJ9.eyJhcHBfdHlwZSI6InN5c3RlbSIsInVzZXJfbmFtZSI6ImFkYW11d2VlQGdtYWlsLmNvbSIsImVubF9jaWQiOiIiLCJlbmxfcGFzc3dvcmRfbGFzdF9jaGFuZ2VkIjoiMTU5MTYzMDMwOSIsImF1dGhvcml0aWVzIjpbIlJPTEVfVVNFUiJdLCJjbGllbnRfaWQiOiI1ZTZjMjFlODY3NTFjY2EyM2M4NGI0OTY3MTI1Y2E5YyIsImF1ZCI6WyJvYXV0aDItcmVzb3VyY2UiXSwiaXNfaW50ZXJuYWxfYXBwIjpmYWxzZSwic2NvcGUiOlsicmVhZCIsIndyaXRlIl0sImF0aSI6IjJkMzRhYmZiLTdlOTYtNDc2MS1hNjg0LTNmOTkzYTU1NWFmNCIsImV4cCI6MTY3NjMzNjg3NiwiZW5sX3VpZCI6IjE5NjUxMzMiLCJqdGkiOiI3Mjc1OTdkMi1iZGIxLTRhOTQtYjMwZC1jMjY0OTZhZmNhZDIifQ.aimoOAX5g1nrheo2SQ8aDcFQpaSQSKr3lp2w1-afLi7CfMxjDSsq5assObUjwTxZ7Rh7YgOloA2aXiKzwA2EWvPkgomAeVjQOT1m3eZKmcWCNmYIg2imD5AqY5d5oxIR3K0NVyGG9t9wl16kGGkL1F3BroMEB91Baok3kAoD9Tc"
    api_key = "9bc320b6b67573fa1bdff67d8e8e869b"
    system_id = '1816626'
    client_id = '5e6c21e86751cca23c84b4967125ca9c'
    client_secret ='781a2c002f6d657e6c21eb20ffc3bb1e'
    passcode = 'IVXjEx'
    api_url = "api.enphaseenergy.com"

    def __init__(self, config_file_path) -> None:
        # Attempt to load config if it exists
        if (config_file_path != "" and exists(config_file_path)):
            pass


        else:
            # Use default values
            pass

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
    enphase = EnphaseV4()
    client = OHClient()
    # Loop forever
    delay_minutes = 5
    while True:
        # Get Battery Charge
        print("---------------------------------------------------------------------------------------")
        charge = enphase.get_battery_charge()
        enphase._debug_print("battery charge = " + str(charge) + "%")
        # Post to OpenHab
        client.publish_value("BatteryCharge", charge)
        # Pause
        time.sleep(delay_minutes * 60)
