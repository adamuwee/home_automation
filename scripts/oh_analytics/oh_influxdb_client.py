
import sys
from datetime import datetime
import logging


from influxdb_client import InfluxDBClient
from influxdb_client.rest import ApiException

import jsonpickle
from os.path import exists

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
        self._client = None
        pass
    
    # Read / Create the server config file including the connection info
    def _init_server_conf(self):
        # Locals
        json_file_name = 'influxdb_conf.json'

        # Check if conf file exists
        if not exists(json_file_name):
            self._logger.error(f'{json_file_name} not found. Creating default and exiting.')
            # Create default conf file with placeholder values
            self._connection_conf['url'] = "<URL of InfluxDB Server including port number. Example: ""http://localhost:9999"">"
            self._connection_conf['token'] = '<Token generated by InfluxDB Server>'
            self._connection_conf['org'] = "<Organization Name (probably still_creek)>"
            self._connection_conf['bucket'] = "<Bucket name (probably home_iot)>"
            with open(json_file_name, 'w') as conf_file:
                conf_file.write(jsonpickle.encode(self._connection_conf)) 
                self._logger.info(f'Default conf file created: {json_file_name}. Please update before running this script.')
            sys.exit()

        # Read conf
        try:
            with open(json_file_name, 'r') as conf_file:
                self._connection_conf = jsonpickle.decode(conf_file.read())
                self._logger.info(f'JSON conf loaded:\n{self._connection_conf}')
        except:
            self._logger.error('Error occured while reading JSON conf file.')
            sys.exit()

    # Connect to the InfluxDB Server
    def _connect(self) -> bool:
        if self._client == None:
            try:
                self._logger.info('Connecting to InfluxDB Server...')
                self._client = InfluxDBClient(url=self._connection_conf['url'], 
                                              token=self._connection_conf['token'], 
                                              org=self._connection_conf['org'])

                self._logger.info('Connected to InfluxDB Server.')
                self._check_connection()
                self._check_query()
            except Exception as e:
                self._logger.warn(f"Error connecting to InfluxDB Server: {e}")               
        return (self._client is not None)
    
    def _check_connection(self):
        """Check that the InfluxDB is running."""
        self._logger.info("> Checking connection...")
        self._client.api_client.call_api('/ping', 'GET')
        self._logger.info("ok")


    def _check_query(self):
        """Check that the credentials has permission to query from the Bucket"""
        self._logger.info("> Checking credentials for query ...")
        try:
            self._client.query_api().query(f"from(bucket:\"{self._connection_conf['bucket']}\") |> range(start: -1m) |> limit(n:1)", self._connection_conf['org'])
        except ApiException as e:
            # missing credentials
            if e.status == 404:
                raise Exception(f"The specified token doesn't have sufficient credentials to read from '{self._connection_conf['bucket']}' "
                                f"or specified bucket doesn't exists.") from e
            raise
        self._logger.info("ok")

    # Get the list of items from the OpenHab Database
    # < --- INCOMPLETE - NEEDS TO BE IMPLEMENTED --- >
    def get_item_list(self) -> dict:
        # Get the last value over the last 30 days
        query = f'''
        from(bucket: "{self._connection_conf['bucket']}")
        |> range(start: -1y)
        |> keep(columns: ["_measurement"])
        |> distinct(column: "_measurement")
        '''
        result = self._basic_query(query)
        
        # Process the result
        if result and len(result) > 0 and len(result[0].records) > 0:
            records = [record.values for table in result for record in table.records]
            return records
        else:
            return None

    # Provides the basic query interface to the InfluxDB Server
    def _basic_query(self, query) -> dict:
        # (Re-)Connect to OH Database
        if not self._connect():
            return None
        # Execute Flux Query
        query_api = self._client.query_api()
        result = query_api.query(org=self._connection_conf['org'], query=query)
        return result
        
    # Get the last value for a given OpenHab item name. Return None if not found.
    def get_last_value(self, oh_item_name) -> dict:
        # Get the last value over the last 30 days
        query = f'''
        from(bucket: "{self._connection_conf['bucket']}")
        |> range(start: -30d)
        |> filter(fn: (r) => r["_measurement"] == "{oh_item_name}")
        |> filter(fn: (r) => r["_field"] == "value")
        |> filter(fn: (r) => r["item"] == "{oh_item_name}")
        |> last()
        '''
        result = self._basic_query(query)
        
        # Process the result
        if result and len(result) > 0 and len(result[0].records) > 0:
            last_value = result[0].records[0].values['_value']
            return last_value
        else:
            return None
        
    # Get the number of rows (measurement points) for a given OpenHab item name. Return None if not found.
    def get_row_count(self, oh_item_name) -> int:
        # Get the row count
        query = f'''
        from(bucket: "{self._connection_conf['bucket']}")
        |> range(start: 2021-01-01T00:00:00Z, stop: now())
        |> filter(fn: (r) => r["_measurement"] == "{oh_item_name}")
        |> count()
        |> yield(name: "count")
        '''
        
        result = self._basic_query(query)

        # Process the result - the result is the 'count' and _not_ all of the rows
        if result and len(result) > 0 and len(result[0].records) > 0:
            row_count = result[0].records[0].values['_value']
            return row_count
        else:
            return None

    # < --- INCOMPLETE - NEEDS TO BE IMPLEMENTED --- >    
    def get_values_for_day(self, oh_item_name, day) -> dict:
        # Set start and end times for the day
        startDate = datetime(day.year, day.month, day.day, 0, 0, 0).isoformat() + "Z"
        endDate = datetime(day.year, day.month, day.day, 23, 59, 59).isoformat() + "Z"
        # Flux query for all records for the given day
        query = f'''
        from(bucket: "{self._connection_conf['bucket']}")
        |> range(start: {startDate}, stop: {endDate})
        |> filter(fn: (r) => r["_measurement"] == "{oh_item_name}")
        '''
        # Run it.
        result = self._basic_query(query)
        # Process the result - the result is the 'count' and _not_ all of the rows
        if result and len(result) > 0 and len(result[0].records) > 0:
            records = [record.values for table in result for record in table.records]
            return records
        else:
            return None

    # Gets the first value for a given OpenHab item name for a given day. Return None if not found.
    def get_first_value_for_day(self, oh_item_name, day) -> dict:
        # Set start and end times for the day
        startDate = datetime(day.year, day.month, day.day, 0, 0, 0).isoformat() + "Z"
        endDate = datetime(day.year, day.month, day.day, 23, 59, 59).isoformat() + "Z"
        # Flux query for all records for the given day
        query = f'''
        from(bucket: "{self._connection_conf['bucket']}")
        |> range(start: {startDate}, stop: {endDate})
        |> filter(fn: (r) => r["_measurement"] == "{oh_item_name}")
        |> first()
        '''
        # Run it.
        result = self._basic_query(query)
        # Process the result - the result is the 'count' and _not_ all of the rows
        if result and len(result) > 0 and len(result[0].records) > 0:
            first_value = result[0].records[0].values['_value']
            return first_value
        else:
            return None

    # Gets all the records for a given OpenHab item name for a given month. Return None if not found.
    def get_values_for_month(self, oh_item_name, month) -> dict:
        startDate = month
        startDate = datetime(month.year, month.month, 1, 0, 0, 0).isoformat() + "Z"
        if (month.month == 12):
            # Change to the next year / January
            endDate = datetime(month.year+1, 1, 1, 0, 0, 0).isoformat() + "Z"
        else:
            endDate = datetime(month.year, month.month+1, 1, 0, 0, 0).isoformat() + "Z"
        # Flux query for all records for the given month
        query = f'''
        from(bucket: "{self._connection_conf['bucket']}")
        |> range(start: {startDate}, stop: {endDate})
        |> filter(fn: (r) => r["_measurement"] == "{oh_item_name}")
        '''
        # Run it.
        result = self._basic_query(query)
        # Process the result - the result is the all of the records
        if result and len(result) > 0 and len(result[0].records) > 0:
            records = [record.values for table in result for record in table.records]
            return records
        else:
            return None

    # Gets the first value for the given month
    def get_first_value_for_month(self, oh_item_name, month) -> dict:
        startDate = month
        startDate = datetime(month.year, month.month, 1, 0, 0, 0).isoformat() + "Z"
        if (month.month == 12):
            # Change to the next year / January
            endDate = datetime(month.year+1, 1, 1, 0, 0, 0).isoformat() + "Z"
        else:
            endDate = datetime(month.year, month.month+1, 1, 0, 0, 0).isoformat() + "Z"
        # Flux query for all records for the given month
        query = f'''
        from(bucket: "{self._connection_conf['bucket']}")
        |> range(start: {startDate}, stop: {endDate})
        |> filter(fn: (r) => r["_measurement"] == "{oh_item_name}")
        |> first()
        '''
        # Run it.
        result = self._basic_query(query)
        # Process the result - the result is the all of the records
        if result and len(result) > 0 and len(result[0].records) > 0:
            first_value = result[0].records[0].values['_value']
            return first_value
        else:
            return None
    
    # < --- INCOMPLETE - NEEDS TO BE IMPLEMENTED --- >
    def get_all_values(self, oh_item_name) -> dict:
        # Flux query for all records for the given month
        query = f'''
        from(bucket: "{self._connection_conf['bucket']}")
        |> range(start: 2021-01-01T00:00:00Z, stop: now())
        |> filter(fn: (r) => r["_measurement"] == "{oh_item_name}")
        '''
        # Run it.
        result = self._basic_query(query)
        # Process the result
        if result and len(result) > 0:
            records = [record.values for table in result for record in table.records]
            return records
        else:
            return None

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
    osc = oh_influxdb_client(logger)
    items_list = osc.get_item_list()
    logger.info(f'TEST #1 - OH3 Items List: {len(items_list)} items')
    logger.info(f'TEST #2 - Get Last Value of Water_Mains_Water_Mains_Count_Scale_Gallons: ' + str(osc.get_last_value('Water_Mains_Water_Mains_Count_Scale_Gallons')))
    logger.info(f'TEST #3 - Get Row Count of Water_Mains_Water_Mains_Count_Scale_Gallons: ' + str(osc.get_row_count('Water_Mains_Water_Mains_Count_Scale_Gallons')))
    logger.info(f'TEST #4 - Get Measurements of Water_Mains_Water_Mains_Count_Scale_Gallons for a given day: ' + str(len(osc.get_values_for_day('Water_Mains_Water_Mains_Count_Scale_Gallons', datetime.now()))) + ' measurements')
    logger.info(f'TEST #5 - Get Measurements of Water_Mains_Water_Mains_Count_Scale_Gallons for a given day: ' + str(len(osc.get_values_for_month('Water_Mains_Water_Mains_Count_Scale_Gallons', datetime.now()))) + ' measurements')
    logger.info(f'TEST #6 - Get First Measurements of Water_Mains_Water_Mains_Count_Scale_Gallons for a given day: ' + str(osc.get_first_value_for_day('Water_Mains_Water_Mains_Count_Scale_Gallons', datetime.now())))
    logger.info(f'TEST #7 - Get First Measurements of Water_Mains_Water_Mains_Count_Scale_Gallons for a given month: ' + str(osc.get_first_value_for_month('Water_Mains_Water_Mains_Count_Scale_Gallons', datetime.now())))
    logger.info(f'TEST #8 - Get All Measurements of Water_Mains_Water_Mains_Count_Scale_Gallons: ' + str(len(osc.get_all_values('Water_Mains_Water_Mains_Count_Scale_Gallons'))) + ' measurements')
    
if __name__ == "__main__":
    main()
