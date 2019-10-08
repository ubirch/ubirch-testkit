import binascii
import logging
import time
from uuid import UUID

import umsgpack as msgpack
import urequests as requests

from .ubirch_client import UbirchClient

logger = logging.getLogger(__name__)


class UbirchDataClient:

    def __init__(self, uuid: UUID, cfg: dict):
        """
        Initialize the ubirch client with the service URLs and header with device UUID and password for authentication.
        """
        self.__uuid = uuid
        self.__auth = cfg['password']
        self.__headers = {
            'X-Ubirch-Hardware-Id': str(uuid),
            'X-Ubirch-Credential': binascii.b2a_base64(self.__auth).decode('utf-8').rstrip('\n'),
            'X-Ubirch-Auth-Type': 'ubirch'
        }
        if 'data' in cfg:
            self.__data_service_url = cfg['data']
        else:
            self.__data_service_url = "https://data.{}.ubirch.com/v1/msgPack".format(cfg['env'])

        if 'keyService' in cfg:
            key_service_url = cfg['keyService']
        else:
            key_service_url = "https://key.{}.ubirch.com/api/keyService/v1/pubkey/mpack".format(cfg['env'])

        if 'niomon' in cfg:
            auth_service_url = cfg['niomon']
        else:
            auth_service_url = "https://niomon.{}.ubirch.com".format(cfg['env'])

        # this client generates a new key pair and registers the public key at the key service
        self.__ubirch = UbirchClient(uuid, self.__headers, key_service_url, auth_service_url)

        self.__msg_type = 0

    def pack_message(self, data: dict) -> bytes:
        """
        Generate a message for sending to the ubirch data service.
        :param data: a map containing the data to be sent
        :return: a msgpack formatted array with the device UUID, message type, timestamp and data
        """
        msg = [
            self.__uuid.bytes,
            self.__msg_type,
            int(time.time()),
            data
        ]

        serialized = msgpack.packb(msg)
        logger.debug(binascii.hexlify(serialized))
        return serialized

    def send(self, data: dict):
        """
        Pack the data with UUID and timestamp and send to ubirch data service. On success, send certificate
        of the message to ubirch authentication service. Throws exception if message couldn't be sent or
        response couldn't be verified.
        :param data: a map containing the data to be sent
        """
        print("** sending measurements ...")
        # pack data in a msgpack formatted message with device UUID, message type and timestamp
        message = self.pack_message(data)

        # send message to ubirch data service (only send UPP if successful)
        r = requests.post(self.__data_service_url, headers=self.__headers, data=binascii.hexlify(message))

        if r.status_code == 200:
            r.close()
            # send UPP to niomon
            self.__ubirch.send(message)
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.__data_service_url, r.status_code,
                                                                         r.text))
