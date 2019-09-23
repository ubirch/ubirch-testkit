import urequests as requests
from uuid import UUID
import time

class UbirchDataClient:

    def __init__(self, uuid: UUID, auth: str):
        self.__uuid = uuid
        self.__url = 'https://data.dev.ubirch.com/v1/'
        self.__auth = auth
        self.__headers = {'X-Ubirch-Hardware-Id': str(self.__uuid), 'X-Ubirch-Credential': self.__auth}

    def send(self, data_point):
        data = {'date': int(time.time()), 'data': data_point}

        r = requests.post(self.__url, headers=self.__headers, json=data)

        if r.status_code == 200:
            print("** success".format(self.__url, r.content))
        else:
            print("!! request to {} failed with {}: {}".format(self.__url, r.status_code, r.text))
