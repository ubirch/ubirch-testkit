import binascii
import logging
import urequests as requests
from uuid import UUID

logger = logging.getLogger(__name__)


class API:
    """ubirch API accessor methods."""

    def __init__(self, cfg: dict):
        try:
            self.key_service_url = cfg['keyService']
            self.data_service_url = cfg['data']
            self.auth_service_url = cfg['niomon']
            self.verification_service_url = cfg['verify']
            self._ubirch_headers = {
                'X-Ubirch-Hardware-Id': None,   # just a placeholder, UUID is inserted to header at method call
                'X-Ubirch-Credential': binascii.b2a_base64(cfg['password']).decode().rstrip('\n'),
                'X-Ubirch-Auth-Type': 'ubirch'
            }
        except KeyError:
            raise Exception("incomplete config")    # TODO better error message

    def register_identity(self, key_registration: bytes) -> requests.Response:
        """
        Register an identity at the key service.
        :param key_registration: the key registration data
        :return: the response from the server
        """
        logger.debug("** sending key registration message to " + self.key_service_url)
        return requests.post(self.key_service_url,
                             headers={'Content-Type': 'application/octet-stream'},
                             data=key_registration)

    def send_upp(self, uuid: UUID, upp: bytes) -> requests.Response:
        """
        Send data to the authentication service. Requires encoding before sending.
        :param uuid: the sender's UUID
        :param upp: the msgpack encoded data to send (UPP)
        :return: the response from the server
        """
        logger.debug("** sending UPP to " + self.auth_service_url)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return requests.post(self.auth_service_url,
                             headers=self._ubirch_headers,
                             data=upp)

    def send_data(self, uuid: UUID, message: bytes) -> requests.Response:
        """
        Send a message to the ubirch data service.
        :param uuid: the sender's UUID
        :param message: the message to send to the data service
        :return: the response from the server
        """
        logger.debug("** sending data message to " + self.data_service_url)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return requests.post(self.data_service_url,
                             headers=self._ubirch_headers,
                             data=binascii.hexlify(message))

    def verify(self, data: bytes, quick=False) -> requests.Response:
        """
        Verify a given hash at the verification service. Returns all available verification data.
        :param data: the hash of the message to verify
        :param quick: only run quick check to verify that the hash has been stored in backend
        :return: the response from the server (if the verification was successful and the data related to it)
        """
        url = self.verification_service_url
        if not quick:
            url = url + '/verify'
        logger.debug("** verifying hash: {} ({})".format(binascii.b2a_base64(data).decode(), url))
        return requests.post(url,
                             headers={'Accept': 'application/json', 'Content-Type': 'text/plain'},
                             data=binascii.b2a_base64(data).decode().rstrip('\n'))
