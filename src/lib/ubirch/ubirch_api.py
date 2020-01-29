import binascii
import logging
import urequests as requests
from uuid import UUID

logger = logging.getLogger(__name__)


class API:
    """ubirch API accessor methods."""

    def __init__(self, uuid: UUID, auth: str):
        self._headers = {
            'X-Ubirch-Hardware-Id': str(uuid),
            'X-Ubirch-Credential': binascii.b2a_base64(auth).decode().rstrip('\n'),
            'X-Ubirch-Auth-Type': 'ubirch'
        }

    def register_identity(self, url: str, key_registration_message: bytes) -> requests.Response:
        """
        Register an identity at the key service.
        :param url: the URL of the key service
        :param key_registration_message: the key registration data
        :return: the response from the server
        """
        logger.debug("** sending key registration message to " + url)
        return requests.post(url,
                             headers={'Content-Type': 'application/octet-stream'},
                             data=key_registration_message)

    def send_upp(self, url: str, upp: bytes) -> requests.Response:
        """
        Send data to the authentication service. Requires encoding before sending.
        :param url: the URL of the authentication service
        :param upp: the msgpack encoded data to send (UPP)
        :return: the response from the server
        """
        logger.debug("** sending UPP to " + url)
        return requests.post(url, headers=self._headers, data=upp)

    def send_data(self, url: str, message: bytes) -> requests.Response:
        """
        Send a message to the ubirch data service.
        :param url: the URL of the data service
        :param message: the message to send to the data service
        :return: the response from the server
        """
        logger.debug("** sending data message to " + url)
        return requests.post(url, headers=self._headers, data=binascii.hexlify(message))

    def verify(self, url: str, data: bytes) -> requests.Response:
        """
        Verify a given hash at the verification service. Returns all available verification data.
        :param url: the URL of the data service
        :param data: the hash of the message to verify
        :return: the response from the server (if the verification was successful and the data related to it)
        """
        logger.debug("** verifying hash: {} ({})".format(binascii.b2a_base64(data).decode(), url))
        return requests.post(url,
                             headers={'Accept': 'application/json', 'Content-Type': 'text/plain'},
                             data=binascii.b2a_base64(data).decode())
