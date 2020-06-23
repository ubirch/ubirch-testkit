import urequests as requests
from ubinascii import b2a_base64
from uuid import UUID


def _send_request(url: str, data: bytes, headers: dict) -> (int, bytes):
    """
    Send a http post request to the backend.
    :param url: the backend service URL
    :param data: the data to send to the backend
    :param headers: the headers for the request
    :return: the backend response status code, the backend response content (body)
    """
    r = requests.post(url=url, data=data, headers=headers)
    return r.status_code, r.content


class API:
    """ubirch API accessor methods."""

    def __init__(self, cfg: dict):
        self.debug = cfg['debug']
        self.env = cfg['env']
        self.identity_service_url = cfg['identity']
        self.data_service_url = cfg['data']
        self.auth_service_url = cfg['niomon']
        self.bootstrap_service_url = cfg['bootstrap']
        self._ubirch_headers = {
            'X-Ubirch-Credential': b2a_base64(cfg['password']).decode().rstrip('\n'),
            'X-Ubirch-Auth-Type': 'ubirch'
        }

    def send_upp(self, uuid: UUID, upp: bytes) -> (int, bytes):
        """
        Send data to the authentication service. Requires encoding before sending.
        :param uuid: the sender's UUID
        :param auth: the ubirch backend auth token (password)
        :param upp: the msgpack encoded data to send (UPP)
        :return: the server response status code, the server response content (body)
        """
        if self.debug:
            print("** sending UPP to " + self.auth_service_url)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return _send_request(url=self.auth_service_url,
                             data=upp,
                             headers=self._ubirch_headers)

    def send_data(self, uuid: UUID, message: bytes) -> (int, bytes):
        """
        Send a JSON data message to the ubirch data service. Requires encoding before sending.
        :param uuid: the sender's UUID
        :param auth: the ubirch backend auth token (password)
        :param message: the encoded JSON message to send to the data service
        :return: the server response status code, the server response content (body)
        """
        if self.debug:
            print("** sending data message to " + self.data_service_url + "/json")
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return _send_request(url=self.data_service_url + "/json",
                             data=message,
                             headers=self._ubirch_headers)

    def bootstrap_sim_identity(self, imsi: str) -> (int, bytes):
        """
        Claim SIM identity at the ubirch backend.
        The response contains the SIM applet PIN to unlock crypto functionality.
        :param imsi: the SIM international mobile subscriber identity (IMSI)
        :param auth: the ubirch backend auth token (password)
        :return: the server response
        """
        if self.debug:
            print("** bootstrapping identity {} at {}".format(imsi, self.bootstrap_service_url))
        self._ubirch_headers['X-Ubirch-IMSI'] = imsi
        r = requests.get(url=self.bootstrap_service_url, headers=self._ubirch_headers)
        del self._ubirch_headers['X-Ubirch-IMSI']
        return r.status_code, r.content

    def send_csr(self, csr: bytes) -> (int, bytes):
        """
        Send a X.509 Certificate Signing Request to the ubirch identity service
        :param csr: the CSR in der format (binary)
        :return: the server response status code, the server response content (body)
        """
        if self.debug: print("** sending CSR to " + self.identity_service_url)
        return _send_request(url=self.identity_service_url,
                             data=csr,
                             headers={'Content-Type': 'application/octet-stream'})
