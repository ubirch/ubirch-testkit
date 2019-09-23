import urequests as requests
from uuid import UUID
import time

class UbirchDataClient:

    def __init__(self, uuid: UUID, cfg: dict):
        self.__uuid = uuid
        self.__auth = cfg['password']
        self.__keyService_url = cfg['keyService']
        self.__niomon_url = cfg['niomon']
        self.__data_url = cfg['data']
        self.__headers = {'X-Ubirch-Hardware-Id': str(self.__uuid), 'X-Ubirch-Credential': self.__auth}

    def send(self, data_point):
        data = {'date': int(time.time()), 'data': data_point}

        r = requests.post(self.__data_url, headers=self.__headers, json=data)

        if r.status_code == 200:
            print("** success")
        else:
            print("!! request to {} failed with {}: {}".format(self.__data_url, r.status_code, r.text))
