'''
This script is used to handle data from openweathermap
- Collect data via api calls
- Transform data
'''
import pymongo
import requests
import time
from datetime import datetime, timedelta
from abc import abstractmethod

MAX_ATTEMPTS = 10 # Number of retrying attempts to get data
SLEEP_TIME_FOR_REQUEST = 0.5


class Updater:
    '''
    Description:
    - This class is used to retrieve data from openweathermap 
    and store them in mongodb database
    '''

    def __init__(self, connection_string: str, dbname: str):
        '''
        Parameters:
        - connection_string: MongoDB connection string
        - dbname: name of the database

        Description:
        - Establish connection to MongoDB server
        '''
        self._db = None
        client = pymongo.MongoClient(connection_string)
        self._db = client.get_database(dbname)
        self._api_key = '4ce6dbd5661bd1a387f31884de79b6c2'

    def _transform_api(self, jsondata: dict, region_name: str, modified_time: str):
        '''
        This function will convert raw json data to a formatted one 
        '''
        return {
            'Time': modified_time,
            'Temperature': round(jsondata['main']['temp'] - 272.15, 0),
            'Wind': jsondata['wind']['speed'],
            'Humidity': jsondata['main']['humidity'],
            'Pressure': jsondata['main']['pressure'],
            'Place': region_name
        }

    @abstractmethod
    def _query_func(self, collection, **kwargs):
        pass

    def update(self, collname: str):
        '''
        Parameters:
        - collname: collection name

        Description:
        - Based on data from region_data collection
        collect data from openweather api and update the data
        in the provided collectionl name

        Returns:
        - bool: update status
        '''

        # Check for region_data existence
        if 'region_data' not in self._db.list_collection_names():
            raise Exception('region_data did not exists')

        # Set cursors
        region_data_collection = self._db.get_collection('region_data')

        # Filter data
        regions_data = region_data_collection.find(
            {}, {'_id': False, 'id': True, 'Place': True})

        # Get current time
        now = (datetime.now() + timedelta(hours=7)).replace(second=0).strftime("%Y-%m-%dT%H:%M:%S")

        data = []
        for region in regions_data:
            api_url = f'https://api.openweathermap.org/data/2.5/weather?id={region["id"]}&appid={self._api_key}'
            
            nb_attempts = 0
            jsondata = None
            
            while nb_attempts < MAX_ATTEMPTS:
                nb_attempts += 1
                time.sleep(SLEEP_TIME_FOR_REQUEST)

                response = requests.get(api_url)
                if response.ok == True:
                    try:
                        jsondata = response.json()
                        # Transform data
                        jsondata = self._transform_api(
                        jsondata,
                        region['Place'],
                        now)
                        # Store data
                        data.append(jsondata)
                        break
                    except: 
                        continue
            
            # Stop and wait for next api call
            if nb_attempts == MAX_ATTEMPTS:
                return False

        # Nothing was crawled
        if len(data) == 0:
            return False

        # Update data
        self._query_func(collname=collname,
                         data=data, region=region)

        return True


class UpdaterRealtime(Updater):
    '''
    Description:
    - This clas is used to update weather data every 1 minute
    '''

    def __init__(self, connection_string: str, dbname: str):
        super().__init__(connection_string, dbname)

    def _query_func(self, collname, **kwargs):
        # Create index if the collection does not exists
        create_index = False
        if collname not in self._db.list_collection_names():
            create_index = True
        
        # Update
        collection = self._db.get_collection(collname)
        for data in kwargs['data']:
            collection.find_one_and_update(
                {'Place': kwargs['region']['Place']},
                {'$set': data},
                upsert=True,
            )
        
        # Create index
        if create_index == True:
            collection.create_index('Place')


class UpdaterInterval(Updater):
    '''
    Description:
    - This clas is used to update weather data every 30 minutes
    '''
    def __init__(self, connection_string: str, dbname: str):
        super().__init__(connection_string, dbname)

    def _query_func(self, collname, **kwargs):
        collection = self._db.get_collection(collname)
        return collection.insert_many(kwargs['data'])