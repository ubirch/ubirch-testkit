from uuid import UUID
import umsgpack as msgpack
import urequests as requests
import time
import json
import binascii

from .ubirch_client import *

class UbirchDataClient:

    def __init__(self, uuid: UUID, cfg: dict):
        self.__uuid = uuid
        self.__auth = cfg['password']
        self.__keyService_url = cfg['keyService']
        self.__niomon_url = cfg['niomon']
        self.__data_url = cfg['data']
        self.__headers = {'X-Ubirch-Hardware-Id': str(self.__uuid), 'X-Ubirch-Credential': self.__auth}

        # this client will generate a new key pair and register it at the ubirch key service
        self.__ubirch = UbirchClient(uuid, self.__headers)

    def send(self, data: dict):
        print("** sending data to ubirch data service ...")
        # pack data as message with uuid and timestamp
        msg = {'uuid': self.__uuid.bytes, 'timestamp': int(time.time()), 'data': data}

        # convert the message into msgpack format
        msgpacked_msg = bytearray(msgpack.packb(msg, use_bin_type=True))

        # send message in msgpack format to ubirch data service
        print(binascii.hexlify(msgpacked_msg))
        r = requests.post(self.__data_url, headers=self.__headers, data=msgpacked_msg)

        if r.status_code == 200:
            print("** success")
        else:
            print("!! request to {} failed with {}: {}".format(self.__data_url, r.status_code, r.text))

        # send UPP to niomon
        print("** sending measurement certificate ...")
        self.__ubirch.send(data)
