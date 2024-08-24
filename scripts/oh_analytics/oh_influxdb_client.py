
import sys
from datetime import datetime
import logging
from typing import Any
import mariadb
import json
from os.path import exists
import os

class oh_influxdb_client():

    # OH SQL Client Globals
    _logger = None
    _connection = None
    _connection_conf = dict()

    _user = None
    _user_pwd = None
    _host = None
    _port = 3306
    _database = None

    def __init__(self, logger) -> None:
        if logger == None:
            # Configure Logger
            logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
            self._logger = logging.getLogger(__name__)
        else:
            self._logger = logger
        self._logger.info('OH SQL Client object init')
        self._connection = None
        self._init_server_conf()
        pass
    
    def _init_server_conf(self):
        # Locals
        json_file_name = 'sql_conf.json'

        # Create conf entries
        self._connection_conf['user_name'] = 'SQL User Name'
        self._connection_conf['user_pwd'] = 'SQL User Name Password'
        self._connection_conf['host'] = 'OH SQL Host Name'
        self._connection_conf['port'] = '3306'
        self._connection_conf['database_name'] = 'OH Database Name on SQL Server'

        # Read json conf
        try:
            with open(json_file_name, 'r') as json_conf_file:
                self._logger.info(f'Reading {self._connection_conf}: {os.path.abspath(os.getcwd())}')
                json_data = json_conf_file.read()
                json_conf_file.close()
            json_obj = json.loads(json_data)
            self._connection_conf['user_name'] = json_obj['user_name']
            self._connection_conf['user_pwd'] = json_obj['user_pwd']
            self._connection_conf['host'] = json_obj['host']
            self._connection_conf['port'] = json_obj['port']
            self._connection_conf['database_name'] = json_obj['database_name']
            self._logger.info(f'JSON conf loaded:\n{self._connection_conf}')
        except:
            self._logger.error('Error occured while reading JSON conf file.')
            # Attempt to create default conf file
            file_exists = exists(json_file_name)
            if file_exists:
                self._logger.error(f'Cannot read conf file: {json_file_name}\rExiting.')
                sys.exit()
            else:
                self._logger.info('Attempting to create default JSON conf file.')
                json_object = json.dumps(self._connection_conf, indent = 4)
                with open(json_file_name, "w") as outfile:
                    outfile.write(json_object)
                self._logger.info(f'Default conf file written: {json_file_name}\nPlease modify conf file for your system.\nExiting.')
                sys.exit()

    def _connect(self) -> Any:
        if self._connection == None:
            try:
                self._logger.info('Connecting to SQL Server...')
                self._connection = mariadb.connect(
                    user=self._connection_conf['user_name'],
                    password=self._connection_conf['user_pwd'],
                    host=self._connection_conf['host'],
                    port=int(self._connection_conf['port']),
                    database=self._connection_conf['database_name']
                )

            except mariadb.Error as e:
                self._logger.warn(f"Error connecting to MariaDB Platform: {e}")
            finally:
                self._logger.info('Connected to SQL Server.')

        if (self._connection == None):
            self._logger.warn("SQL connection failed. Exiting.")
            return None
        else:
            return self._connection.cursor()

    def get_item_list(self) -> dict:
        # Connect to OH Database
        cursor = self._connect()
        if cursor == None:
            return None
        # Build SQL Query    
        query = "SELECT * FROM items;"
        result = None
        cursor.execute(query, result)
        # Building dict < item #, item name >
        item_list = dict()
        for (item_num, item_name) in cursor:
            item_list[item_num] = item_name
        return item_list

    def _get_table_name_from_OH_name(self, oh_item_name) -> str:
        item_list = self.get_item_list()
        item_table_index = list(item_list.keys())[list(item_list.values()).index(oh_item_name)]
        oh_table_name = f'item{item_table_index:04}'
        return oh_table_name

    # Get the last value for a given OpenHab item name. Return None if not found.
    def get_last_value(self, oh_item_name) -> dict:
        oh_table_name = self._get_table_name_from_OH_name(oh_item_name) # In the format itemXXXX
        colName = 'time'
        query = f'SELECT * FROM {oh_table_name} ORDER BY {colName} DESC LIMIT 1'
        # Connect to OH Database
        cursor = self._connect()
        if cursor == None:
            return None
        # Build SQL Query  
        cursor.execute(query)
        return cursor.fetchone()
    
    # Get the number of rows (measurement points) for a given OpenHab item name. Return None if not found.
    def get_row_count(self, oh_item_name) -> int:
        oh_table_name = self._get_table_name_from_OH_name(oh_item_name) # In the format itemXXXX
        colName = 'time'
        query = f'SELECT COUNT(*) FROM {oh_table_name}'
        # Connect to OH Database
        cursor = self._connect()
        if cursor == None:
            return None
        # Execute SQL Query  
        cursor.execute(query)
        return cursor.fetchone()
    
    def get_values_for_day(self, oh_item_name, day) -> dict:
        # Build SQL Query
        oh_table_name = self._get_table_name_from_OH_name(oh_item_name) # In the format itemXXXX
        colName = 'time'
        startDate = day
        startDate = datetime(day.year, day.month, day.day, 0, 0, 0)
        endDate = datetime(day.year, day.month, day.day, 23, 59, 59)
        query = f"SELECT * FROM {oh_table_name} WHERE time >= '{startDate}' AND time < '{endDate}'";
        # Connect to OH Database
        cursor = self._connect()
        if cursor == None:
            return None
        # Execute SQL Query  
        cursor.execute(query)
        # Building dict < item #, item name >
        measurement_list = dict()
        for (time, value) in cursor:
            measurement_list[time] = value
        return measurement_list

    def get_first_value_for_day(self, oh_item_name, day) -> dict:
        # Build SQL Query
        oh_table_name = self._get_table_name_from_OH_name(oh_item_name) # In the format itemXXXX
        colName = 'time'
        startDate = day
        startDate = datetime(day.year, day.month, day.day, 0, 0, 0)
        endDate = datetime(day.year, day.month, day.day, 23, 59, 59)
        query = f"SELECT * FROM {oh_table_name} WHERE time >= '{startDate}' AND time < '{endDate}' LIMIT 1";
        # Connect to OH Database
        cursor = self._connect()
        if cursor == None:
            return None
        # Execute SQL Query  
        cursor.execute(query)
        # Building dict < item #, item name >
        measurement_list = dict()
        for (time, value) in cursor:
            measurement_list[time] = value
        return measurement_list

    def get_values_for_month(self, oh_item_name, month) -> dict:
        # Build SQL Query
        oh_table_name = self._get_table_name_from_OH_name(oh_item_name) # In the format itemXXXX
        colName = 'time'
        startDate = month
        startDate = datetime(month.year, month.month, 1, 0, 0, 0)
        if (month.month == 12):
            # Change to the next year / January
            endDate = datetime(month.year+1, 1, 1, 0, 0, 0)
        else:
            endDate = datetime(month.year, month.month+1, 1, 0, 0, 0)
        query = f"SELECT * FROM {oh_table_name} WHERE time >= '{startDate}' AND time < '{endDate}'";
        # Connect to OH Database
        cursor = self._connect()
        if cursor == None:
            return None
        # Execute SQL Query  
        cursor.execute(query)
        # Building dict < item #, item name >
        measurement_list = dict()
        for (time, value) in cursor:
            measurement_list[time] = value
        return measurement_list

    def get_first_value_for_month(self, oh_item_name, month) -> dict:
        # Build SQL Query
        oh_table_name = self._get_table_name_from_OH_name(oh_item_name) # In the format itemXXXX
        colName = 'time'
        startDate = month
        startDate = datetime(month.year, month.month, 1, 0, 0, 0)
        if (month.month == 12):
            # Change to the next year / January
            endDate = datetime(month.year+1, 1, 1, 0, 0, 0)
        else:
            endDate = datetime(month.year, month.month+1, 1, 0, 0, 0)
        query = f"SELECT * FROM {oh_table_name} WHERE time >= '{startDate}' AND time < '{endDate}' LIMIT 1";
        # Connect to OH Database
        cursor = self._connect()
        if cursor == None:
            return None
        # Execute SQL Query  
        cursor.execute(query)
        # Building dict < item #, item name >
        measurement_list = dict()
        for (time, value) in cursor:
            measurement_list[time] = value
        return measurement_list

    def get_all_values(self, oh_item_name) -> dict:
        # Build SQL Query
        oh_table_name = self._get_table_name_from_OH_name(oh_item_name) # In the format itemXXXX
        query = f"SELECT * FROM {oh_table_name}"
        # Connect to OH Database
        cursor = self._connect()
        if cursor == None:
            return None
        # Execute SQL Query  
        cursor.execute(query)
        # Building dict < item #, item name >
        measurement_list = dict()
        for (time, value) in cursor:
            measurement_list[time] = value
        return measurement_list

def main():
    # Configure Logger
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(message)s")
    logger = logging.getLogger(__name__)
    # Debug File Log
    file = logging.FileHandler("debug_sql_client.log")
    file.setLevel(logging.INFO)
    fileformat = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
    file.setFormatter(fileformat)
    logger.addHandler(file)
    # Critical File Log
    cric_file = logging.FileHandler("critical_sql_client.log")
    cric_file.setLevel(logging.CRITICAL)
    cric_file.setFormatter(fileformat)
    logger.addHandler(cric_file)
    # Create OH3 SQL Client and test functions
    osc = oh_sql_client(logger)
    items_list = osc.get_item_list()
    logger.info(f'TEST #1 - OH3 Items List: {len(items_list)} items')
    logger.info(f'TEST #2 - Get Last Value of WS_Temperature: ' + str(osc.get_last_value('WS_Temperature')))
    logger.info(f'TEST #3 - Get Row Count of WS_Temperature: ' + str(osc.get_row_count('WS_Temperature')))
    logger.info(f'TEST #4 - Get Measurements of WS_Temperature for a given day: ' + str(len(osc.get_values_for_day('WS_Temperature', datetime.now()))) + ' measurements')
    logger.info(f'TEST #5 - Get Measurements of WS_Temperature for a given day: ' + str(len(osc.get_values_for_month('WS_Temperature', datetime.now()))) + ' measurements')
    logger.info(f'TEST #6 - Get First Measurements of WS_Temperature for a given day: ' + str(osc.get_first_value_for_day('WS_Temperature', datetime.now())))
    logger.info(f'TEST #7 - Get First Measurements of WS_Temperature for a given month: ' + str(osc.get_first_value_for_month('WS_Temperature', datetime.now())))
    logger.info(f'TEST #8 - Get All Measurements of WS_Temperature: ' + str(len(osc.get_all_values('WS_Temperature'))) + ' measurements')
    
if __name__ == "__main__":
    main()
