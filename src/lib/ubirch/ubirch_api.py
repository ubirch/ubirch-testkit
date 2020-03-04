import binascii
import logging
import urequests as requests
from uuid import UUID

logger = logging.getLogger(__name__)


class API:
    """ubirch API accessor methods."""

    def __init__(self, cfg: dict):
        self.key_service_url = cfg['keyService']
        self.data_service_url = cfg['data']
        self.auth_service_url = cfg['niomon']
        self.verification_service_url = cfg['verify']
        self.bootstrap_service_url = cfg['boot']
        self._ubirch_headers = {
            'X-Ubirch-Credential': binascii.b2a_base64(cfg['password']).decode().rstrip('\n'),
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

        tries_left = 3
        while tries_left > 0:
            tries_left -= 1
            try:
                r = requests.post(url=url, data=data, headers=headers)
                if r.status_code == 200:
                    return r

                if tries_left > 0:
                    logger.debug(
                        "!! request to {} failed with status code {}: {} \nRetry...\n".format(url, r.status_code,
                                                                                              r.text))
                    r.close()
                else:
                    raise Exception(
                        "!! request to {} failed with status code {}: {}".format(url, r.status_code, r.text))
            except OSError as e:
                # the usocket module sporadically throws an OSError. Just try again when it happens.
                if tries_left > 0:
                    logger.debug("caught {}. Retry...\n".format(e))
                    continue
                else:
                    raise

    def bootstrap_sim_identity(self, imsi: str) -> requests.Response:
        """
        Claim SIM identity at the ubirch backend.
        The response contains the SIM applet PIN to unlock crypto functionality.
        :param imsi: the SIM international mobile subscriber identity (IMSI)
        :return: the response from the server
        """
        logger.debug("** bootstrapping identity {} at {}".format(imsi, self.bootstrap_service_url))
        self._ubirch_headers['X-Ubirch-IMSI'] = imsi
        r = requests.get(self.bootstrap_service_url, headers=self._ubirch_headers)
        del self._ubirch_headers['X-Ubirch-IMSI']
        return r

    def register_identity(self, key_registration: bytes) -> requests.Response:
        """
        Register an identity at the key service.
        Throws an exception if sending request failed
        :param key_registration: the key registration data
        :return: the response from the server
        """
        logger.debug("** sending key registration message to " + self.key_service_url)
        if str(self.key_service_url).endswith("/mpack"):
            return self._send_request(self.key_service_url,
                                      key_registration,
                                      headers={'Content-Type': 'application/octet-stream'})
        else:
            return self._send_request(self.key_service_url,
                                      key_registration,
                                      headers={'Content-Type': 'application/json'})

    def send_upp(self, uuid: UUID, upp: bytes) -> requests.Response:
        """
        Send data to the authentication service. Requires encoding before sending.
        Throws an exception if sending request failed
        :param uuid: the sender's UUID
        :param upp: the msgpack encoded data to send (UPP)
        :return: the response from the server
        """
        logger.debug("** sending UPP to " + self.auth_service_url)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(self.auth_service_url, upp)

    def send_data(self, uuid: UUID, message: bytes) -> requests.Response:
        """
        Send a message to the ubirch data service.
        Throws an exception if sending request failed
        :param uuid: the sender's UUID
        :param message: the message to send to the data service
        :return: the response from the server
        """
        logger.debug("** sending data message to " + self.data_service_url)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(self.data_service_url, binascii.hexlify(message))

    def verify(self, data: bytes, quick=False) -> requests.Response:
        """
        Verify a given hash at the verification service. Returns all available verification data.
        Throws an exception if sending request failed / hash could not be
        :param data: the message hash to verify
        :param quick: only run quick check to verify that the hash has been stored in backend
        :return: the response from the server (if the verification was successful and the data related to it)
        """
        url = self.verification_service_url
        if not quick:
            url = url + '/verify'
        logger.debug("** verifying hash: {} ({})".format(binascii.b2a_base64(data).decode(), url))
        return self._send_request(url,
                                  binascii.b2a_base64(data).decode().rstrip('\n'),
                                  headers={'Accept': 'application/json', 'Content-Type': 'text/plain'})
