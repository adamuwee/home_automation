'''
The purpose of this script is to watch how frequently an OpenHab item is updated. 
If an update has not occured in the specified time, then report and error.
'''
import json

class OpenHabWatchDog:

    def __init__(self) -> None:
        pass

class OHWFTConfig:

    # Private Class Members (do not edit)
    _config_file_path = ""

    def __init__(self, config_file_path) -> None:
        # Private Class Members
        self._default_timeout_seconds = 300
        self_list_of_ignored_items = list()

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
    
