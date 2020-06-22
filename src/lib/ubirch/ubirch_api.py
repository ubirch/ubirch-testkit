import time
import ubinascii as binascii
import urequests as requests
from uuid import UUID


class API:
    """ubirch API accessor methods."""

    def __init__(self, cfg: dict):
        self.debug = cfg['debug']
        self.env = cfg['env']
        self.key_service_url = cfg['keyService']
        self.data_service_url = cfg['data']
        self.auth_service_url = cfg['niomon']
        self.verification_service_url = cfg['verify']
        self.bootstrap_service_url = cfg['bootstrap']
        self.identity_service_url = cfg['identity']
        self._ubirch_headers = {
            'X-Ubirch-Credential': binascii.b2a_base64(cfg['password']).decode().rstrip('\n'),
            'X-Ubirch-Auth-Type': 'ubirch'
        }

    def _send_request(self, url: str, data: bytes, headers: dict) -> (int, bytes):
        """
        Send a http post request to the backend.
        :param url: the backend service URL
        :param data: the data to send to the backend
        :param headers: the headers for the request
        :return: the backend response status code, the backend response content (body)
        """
        r = requests.post(url=url, data=data, headers=headers)
        return r.status_code, r.content

    def register_key(self, key_registration: bytes) -> (int, bytes):
        """
        Register a public key at the key service.
        :param key_registration: the key registration data
        :return: the server response
        """
        if self.debug:
            print("** register public key at " + self.key_service_url)
            print("** key registration message [json]: {}".format(key_registration.decode()))
        return self._send_request(url=self.key_service_url,
                                  data=key_registration,
                                  headers={'Content-Type': 'application/json'})

    def send_upp(self, uuid: UUID, upp: bytes) -> (int, bytes):
        """
        Send data to the authentication service. Requires encoding before sending.
        :param uuid: the sender's UUID
        :param upp: the msgpack encoded data to send (UPP)
        :return: the server response
        """
        if self.debug:
            print("** sending UPP to " + self.auth_service_url)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(url=self.auth_service_url,
                                  data=upp,
                                  headers=self._ubirch_headers)

    def send_data(self, uuid: UUID, message: bytes) -> (int, bytes):
        """
        Send a data message to the ubirch data service. Requires encoding before sending.
        :param uuid: the sender's UUID
        :param message: the msgpack or JSON encoded message to send
        :return: the server response
        """
        if message.startswith(b'{'):
            return self._send_data_json(uuid, message)
        else:
            return self._send_data_mpack(uuid, message)

    def _send_data_json(self, uuid: UUID, message: bytes) -> (int, bytes):
        """
        Send a json formatted data message to the ubirch data service.
        :param uuid: the sender's UUID
        :param message: the json formatted message to send to the data service
        :return: the server response
        """
        if self.debug:
            print("** sending data message to " + self.data_service_url + "/json")
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(url=self.data_service_url + "/json",
                                  data=message,
                                  headers=self._ubirch_headers)

    def _send_data_mpack(self, uuid: UUID, message: bytes) -> (int, bytes):
        """
        Send a msgpack formatted data message to the ubirch data service.
        :param uuid: the sender's UUID
        :param message: the msgpack formatted message to send to the data service
        :return: the server response
        """
        if self.debug:
            print("** sending data message to " + self.data_service_url + "/msgPack")
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(url=self.data_service_url + "/msgPack",
                                  data=binascii.hexlify(message),
                                  headers=self._ubirch_headers)

    def verify(self, data: bytes, quick=False) -> (int, bytes):
        """
        Verify a given hash at the verification service. Returns all available verification data.
        :param data: the message hash to verify
        :param quick: only run quick check to verify that the hash has been stored in backend
        :return: the server response (if the verification was successful and the data related to it)
        """
        url = self.verification_service_url
        if not quick:
            url = url + '/verify'
        if self.debug:
            print("** verifying hash: {} ({})".format(binascii.b2a_base64(data).decode().rstrip('\n'), url))
        return self._send_request(url=url,
                                  data=binascii.b2a_base64(data).decode().rstrip('\n'),
                                  headers={'Accept': 'application/json', 'Content-Type': 'text/plain'})

    def bootstrap_sim_identity(self, imsi: str) -> requests.Response:
        """
        Claim SIM identity at the ubirch backend.
        The response contains the SIM applet PIN to unlock crypto functionality.
        :param imsi: the SIM international mobile subscriber identity (IMSI)
        :return: the server response
        """
        if self.debug:
            print("** bootstrapping identity {} at {}".format(imsi, self.bootstrap_service_url))
        self._ubirch_headers['X-Ubirch-IMSI'] = imsi
        return requests.get(url=self.bootstrap_service_url, headers=self._ubirch_headers)

    def send_csr(self, csr: bytes) -> (int, bytes):
        """
        Send a X.509 Certificate Signing Request to the ubirch identity service
        :param csr: the CSR in der format (binary)
        :return: the server response
        """
        if self.debug: print("** sending CSR to " + self.identity_service_url)
        return self._send_request(url=self.identity_service_url,
                                  data=csr,
                                  headers={'Content-Type': 'application/octet-stream'})
