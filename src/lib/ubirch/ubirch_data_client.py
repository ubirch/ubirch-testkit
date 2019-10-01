import binascii
import json
import time
from uuid import UUID

import umsgpack as msgpack
import urequests as requests
from boot import connect
from network import WLAN

from .ubirch_client import UbirchClient

wlan = WLAN(mode=WLAN.STA)
# load WLAN configuration
with open('boot.json', 'r') as b:
    wlan_cfg = json.load(b)


class UbirchDataClient:

    def __init__(self, uuid: UUID, cfg: dict):
        self.__uuid = uuid
        self.__auth = cfg['password']
        self.__data_service_url = cfg['data']
        self.__headers = {
            'X-Ubirch-Hardware-Id': str(uuid),
            'X-Ubirch-Credential': str(binascii.b2a_base64(self.__auth).decode())[:-1],
            'X-Ubirch-Auth-Type': 'ubirch'
        }
        self.__msg_type = 0

        # this client will generate a new key pair and register the public key at the key service
        self.__ubirch = UbirchClient(uuid, self.__headers, cfg['keyService'], cfg['niomon'])

    def send(self, data: dict):
        # pack data map as message array with uuid, message type and timestamp
        msg = [
            self.__uuid.bytes,
            self.__msg_type,
            int(time.time()),
            data
        ]

        # convert the message to msgpack format
        serialized = msgpack.packb(msg)
        # print(binascii.hexlify(serialized))

        if not wlan.isconnected():
            print("!! lost wifi connection")
            print("-- trying to reconnect ...")
            connect(wlan_cfg('networks'), wlan_cfg('timeout'), wlan_cfg('retries'))

        # send message to ubirch data service (only send UPP if successful)
        print("** sending measurements ...")
        r = requests.post(self.__data_service_url, headers=self.__headers, data=binascii.hexlify(serialized))

        if r.status_code == 200:
            r.close()
            # send UPP to niomon
            print("** sending measurement certificate ...")
            self.__ubirch.send(serialized)
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.__data_service_url, r.status_code,
                                                                         r.text))
