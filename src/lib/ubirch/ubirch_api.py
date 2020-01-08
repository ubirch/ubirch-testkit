import binascii
import hashlib
import time

import logging
import umsgpack as msgpack
import urequests as requests
from uuid import UUID

logger = logging.getLogger(__name__)

KEY_SERVICE = "key"
NIOMON_SERVICE = "niomon"
VERIFICATION_SERVICE = "verify"
DATA_SERVICE = "data"


class API:
    """ubirch API accessor methods."""

    def __init__(self, uuid: UUID, env: str, auth: str):
        self._uuid = uuid
        self._auth = auth
        self._headers = {
            'X-Ubirch-Hardware-Id': str(uuid),
            'X-Ubirch-Credential': binascii.b2a_base64(self._auth).decode().rstrip('\n'),
            'X-Ubirch-Auth-Type': 'ubirch'
        }
        self._services = {
            KEY_SERVICE: "https://key.{}.ubirch.com/api/keyService/v1/pubkey".format(env),
            NIOMON_SERVICE: "https://niomon.{}.ubirch.com/".format(env),
            VERIFICATION_SERVICE: "https://verify.{}.ubirch.com/api/upp".format(env),
            DATA_SERVICE: "https://data.{}.ubirch.com/v1".format(env)
        }

        self._msg_type = 1

    def get_url(self, service: str) -> str or None:
        return self._services.get(service, None)

    def register_identity(self, key_registration: bytes) -> requests.Response:
        """
        Register an identity with the backend.
        :param key_registration: the key registration data
        :return: the response from the server
        """
        logger.debug("register identity: {}".format(binascii.hexlify(key_registration)))
        headers = {'Content-Type': 'application/octet-stream'}
        r = requests.post(self.get_url(KEY_SERVICE) + '/mpack', data=key_registration, headers=headers)
        logger.debug("{}: {}".format(r.status_code, r.content))
        return r

    def send_upp(self, upp: bytes) -> requests.Response:
        """
        Send data to the ubirch niomon service. Requires encoding before sending.
        :param upp: the msgpack encoded data to send (UPP)
        :return: the response from the server
        """
        url = self.get_url(NIOMON_SERVICE)
        print("\n** sending measurement certificate to {} ...".format(url))
        print(binascii.hexlify(upp).decode())

        r = requests.post(url, headers=self._headers, data=upp)
        return r

    def verify(self, data: bytes, quick=False) -> requests.Response:
        """
        Verify a given hash with the ubirch backend. Returns all available verification
        data.
        :param data: the hash of the message to verify
        :param quick: only run quick check to verify that the hash has been stored in backend
        :return: if the verification was successful and the data related to it
        """
        logger.debug("verifying hash: {}".format(binascii.b2a_base64(data).decode()))
        url = self.get_url(VERIFICATION_SERVICE)
        if not quick:
            url = url + '/verify'
        r = requests.post(url,
                          headers={'Accept': 'application/json', 'Content-Type': 'text/plain'},
                          data=binascii.b2a_base64(data).decode())
        logger.debug("{}: {}".format(r.status_code, r.content))
        return r

    def pack_data_message_msgpack(self, data: dict) -> (bytes, bytes):
        """
        Generate a message for the ubirch data service.
        :param data: a map containing the data to be sent
        :return: a msgpack formatted array with the device UUID, message type, timestamp, data and hash
        :return: the hash over the data message
        """
        msg = [
            self._uuid.bytes,
            self._msg_type,
            int(time.time()),
            data,
            0
        ]

        # calculate hash of message (without last array element)
        serialized = msgpack.packb(msg)[0:-1]
        message_hash = hashlib.sha512(serialized).digest()

        # replace last element in array with the hash
        msg[-1] = message_hash
        serialized = msgpack.packb(msg)

        return serialized, message_hash

    def send_data(self, data: dict) -> (requests.Response, bytes):
        """
        Pack the data in a message with device UUID and timestamp and send the message to ubirch data service.
        :param data: a map containing the data to be sent   # TODO client should pack and send separately
        :return: the response from the server, the hash over the sent data message (including uuid and timestamp)
        """
        url = self.get_url(DATA_SERVICE) + '/msgPack'
        print("\n** sending measurements to {} ...".format(url))

        # pack data in a msgpack formatted message with device UUID, message type and timestamp
        message, message_hash = self.pack_data_message_msgpack(data)
        print(binascii.hexlify(message).decode())

        # send message to ubirch data service
        r = requests.post(url, headers=self._headers, data=binascii.hexlify(message))
        logger.debug("{}: {}".format(r.status_code, r.content))
        return r, message_hash
