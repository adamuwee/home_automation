'''
The purpose of this script is to watch how frequently an OpenHab item is updated. 
If an update has not occured in the specified time, then report and error.
'''
import json
import os
import oh_sql_client
from datetime import datetime, timedelta

class OpenHabWatchDog:

    def __init__(self, config_file_path) -> None:
        self._config = OHWFTConfig(config_file_path)

    # Return a dict of items that have stale data
    def test_oh_items(self) -> dict:

        stale_items = dict()

        # Create SQL Client and get list of items
        osc = oh_sql_client.oh_sql_client(None)
        items_list = osc.get_item_list()
        print(f"Checking {len(items_list)} OpenHab items.")

        # Iterate through all items and check last
        for name in items_list.values():
            try:
                # Check if item is to be ignored
                if self._in_ignore_list(name):
                    pass
                else:
                    # Get last data point
                    last_data = osc.get_last_value(name)
                    timestamp = last_data[0]
                    time_span = datetime.now() - last_data[0]
                    #print(f"{name} last reported at {time_span.total_seconds()} seconds ago")
                    timeout = self._config.default_timeout_seconds
                    if self._in_per_item_list(name):
                        # Over-write timeout if in the per-item list. E.g. Enphase Battery charge reports every 45 mintues.
                        timeout = self._config.per_item_timeout[name]
                    if time_span.total_seconds() > timeout:
                        stale_items[name] = int(time_span.total_seconds())
            except:
                pass
        
        # Pass back the list of stale items
        return stale_items
    
    def _in_ignore_list(self, item_name) -> bool:
        ignore = item_name in self._config.list_of_ignored_items
        return ignore

    def _in_per_item_list(self, item_name) -> bool:
        is_special = item_name in self._config.per_item_timeout.keys()
        return is_special
            
class OHWFTConfig:

    def __init__(self, config_file_path) -> None:

        # Private Class Members
        self.config_file_path = config_file_path
        self.default_timeout_seconds = 300
        self.list_of_ignored_items = list()
        self.per_item_timeout = dict()

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
    
if __name__ == "__main__":
    oh_wdt = OpenHabWatchDog("oh_wdt_config.json")
    stale_items = oh_wdt.test_oh_items()
    print(f"Stale OpenHab items ({len(stale_items)}):")
    for item in stale_items.items():
        time_duration = timedelta(seconds=int(item[1]))
        days, seconds = time_duration.days, time_duration.seconds
        hours = days * 24 + seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        print(f"{item[0]} --> {days}d {hours}h {minutes}m {seconds}s")