import binascii

import logging
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
        self._headers = {
            'X-Ubirch-Hardware-Id': str(uuid),
            'X-Ubirch-Credential': binascii.b2a_base64(auth).decode().rstrip('\n'),
            'X-Ubirch-Auth-Type': 'ubirch'
        }
        self._services = {
            KEY_SERVICE: "https://key.{}.ubirch.com/api/keyService/v1/pubkey".format(env),
            NIOMON_SERVICE: "https://niomon.{}.ubirch.com/".format(env),
            VERIFICATION_SERVICE: "https://verify.{}.ubirch.com/api/upp".format(env),
            DATA_SERVICE: "https://data.{}.ubirch.com/v1".format(env)
        }

    def get_url(self, service: str) -> str or None:
        return self._services.get(service, None)

    def register_identity(self, key_registration: bytes) -> requests.Response:
        """
        Register an identity with the backend.
        :param key_registration: the key registration data
        :return: the response from the server
        """
        url = self.get_url(KEY_SERVICE) + '/mpack'
        logger.debug("** sending key registration message to {}".format(url))
        return requests.post(url,
                             headers={'Content-Type': 'application/octet-stream'},
                             data=key_registration)

    def send_upp(self, upp: bytes) -> requests.Response:
        """
        Send data to the ubirch niomon service. Requires encoding before sending.
        :param upp: the msgpack encoded data to send (UPP)
        :return: the response from the server
        """
        url = self.get_url(NIOMON_SERVICE)
        logger.debug("** sending UPP to {} ...".format(url))
        return requests.post(url, headers=self._headers, data=upp)

    def send_data(self, data_message: bytes) -> requests.Response:
        """
        Send a message to the ubirch data service.
        :param data_message: the message to be sent to the data service
        :return: the response from the server
        """
        url = self.get_url(DATA_SERVICE) + '/msgPack'
        logger.debug("** sending data message to {} ...".format(url))
        return requests.post(url, headers=self._headers, data=binascii.hexlify(data_message))

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
        return requests.post(url,
                             headers={'Accept': 'application/json', 'Content-Type': 'text/plain'},
                             data=binascii.b2a_base64(data).decode())
