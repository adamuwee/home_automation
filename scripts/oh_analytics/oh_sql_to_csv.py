from os import times
import oh_sql_client
import datetime

# Create a CSV for a OH uid
# TODO
#   - specify timespan
#   - multiple uids w/ harmonized timestamps

def print_ln(line):
    #print(line)
    pass

# Produce a file name friendly timestamp
def timestamp() -> str:
    ts = str(datetime.datetime.now().isoformat()).replace('.', '_')
    return ts.replace(':', '')

# Print list of OH items to a csv file
item_list_file_prefix = 'oh_items'
def items_to_csv():
    oh_client = oh_sql_client.oh_sql_client(None)
    csv_file_item_list = open(f'{item_list_file_prefix}_{timestamp()}.csv', 'w')
    item_list = oh_client.get_item_list()
    # Print / write to disk
    for id,name in item_list.items():
        line = f'{id},{name}'
        print_ln(line)
        csv_file_item_list.write(line+'\n')
    csv_file_item_list.close()

item_values_file_prefix = 'oh_item'
def all_values_to_csv():
    oh_uid = 'WaterMainsDailyUsage'
    oh_uid = 'WS_Temperature'
    oh_uid = 'EcobeeSensorMasterBedroom_SensorTemperature'

    oh_client = oh_sql_client.oh_sql_client(None)
    csv_file_all_values = open(f'{item_values_file_prefix}_{oh_uid}_values_{timestamp()}.csv', 'w')
    all_values = oh_client.get_all_values(oh_uid)
    # Print / write to disk
    for ts, value in all_values.items():
        line = f'{ts},{value}'
        print_ln(line)
        csv_file_all_values.write(line+'\n')
    csv_file_all_values.close()   


def main():
    items_to_csv()
    all_values_to_csv()

if __name__ == "__main__":
    main()