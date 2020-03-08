import binascii
import json
import logging
import urequests as requests
from uuid import UUID
from config import Config

logger = logging.getLogger(__name__)


class API:
    """ubirch API accessor methods."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._ubirch_headers = {
            'X-Ubirch-Credential': binascii.b2a_base64(cfg.password).decode().rstrip('\n'),
            'X-Ubirch-Auth-Type': 'ubirch'
        }

    def _send_request(self, url: str, data: bytes, headers=None) -> requests.Response:
        """
        Send a http request to the ubirch backend.
        This method accounts for the possibility of an uncritical fail and simply tries again, if sending failed.
        Throws an exception if sending failed several times
        :param url: the backend service URL
        :param data: the data to send to the backend
        :param headers: the headers for the request. If not specified, the standard ubirch headers will be used
        :return: the response from the server
        """
        if headers is None:
            headers = self._ubirch_headers

        tries_left = 2
        while True:
            try:
                return requests.post(url=url, data=data, headers=headers)
            except OSError as e:
                # the usocket module sporadically throws an OSError. Just try again when it happens.
                tries_left -= 1
                if tries_left > 0:
                    logger.debug("caught {}. Retry...\n".format(e))
                    continue
                else:
                    raise

    def register_identity(self, key_registration: bytes) -> requests.Response:
        """
        Register an identity at the key service.
        :param key_registration: the key registration data
        :return: the response from the server
        """
        if str(key_registration).startswith("{"):
            logger.debug("** register identity at " + self.cfg.keyService.rstrip("/mpack"))
            logger.debug("** key registration message [json]: {}".format(json.dumps(key_registration)))
            return self._send_request(self.cfg.keyService.rstrip("/mpack"),
                                      key_registration,
                                      headers={'Content-Type': 'application/octet-stream'})
        else:
            logger.debug("** register identity at " + self.cfg.keyService)
            logger.debug(
                "** key registration message [msgpack]: {}".format(binascii.hexlify(key_registration).decode()))
            return self._send_request(self.cfg.keyService,
                                      key_registration,
                                      headers={'Content-Type': 'application/json'})

    def send_upp(self, uuid: UUID, upp: bytes) -> requests.Response:
        """
        Send data to the authentication service. Requires encoding before sending.
        :param uuid: the sender's UUID
        :param upp: the msgpack encoded data to send (UPP)
        :return: the response from the server
        """
        logger.debug("** sending UPP to " + self.cfg.niomon)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(self.cfg.niomon, upp)

    def send_data(self, uuid: UUID, message: bytes) -> requests.Response:
        """
        Send a message to the ubirch data service.
        :param uuid: the sender's UUID
        :param message: the message to send to the data service
        :return: the response from the server
        """
        logger.debug("** sending data message to " + self.cfg.data)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(self.cfg.data, binascii.hexlify(message))

    def verify(self, data: bytes, quick=False) -> requests.Response:
        """
        Verify a given hash at the verification service. Returns all available verification data.
        :param data: the message hash to verify
        :param quick: only run quick check to verify that the hash has been stored in backend
        :return: the response from the server (if the verification was successful and the data related to it)
        """
        url = self.cfg.verify
        if not quick:
            url = url + '/verify'
        logger.debug("** verifying hash: {} ({})".format(binascii.b2a_base64(data).decode(), url))
        return self._send_request(url,
                                  binascii.b2a_base64(data).decode().rstrip('\n'),
                                  headers={'Accept': 'application/json', 'Content-Type': 'text/plain'})
