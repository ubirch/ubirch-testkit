import time
import ubinascii as binascii
import urequests as requests
from uuid import UUID


class API:
    """ubirch API accessor methods."""

    def __init__(self, cfg: dict):
        self.debug = cfg['debug']
        self.key_service_url = cfg['keyService']
        self.data_service_url = cfg['data']
        self.auth_service_url = cfg['niomon']
        self.verification_service_url = cfg['verify']
        self.bootstrap_service_url = cfg['bootstrap']
        self._ubirch_headers = {
            'X-Ubirch-Credential': binascii.b2a_base64(cfg['password']).decode().rstrip('\n'),
            'X-Ubirch-Auth-Type': 'ubirch'
        }

    def _send_request(self, url: str, data: bytes, headers: dict) -> bytes:
        """
        Send a http post request to the ubirch backend.
        This method accounts for the possibility of an uncritical fail and simply tries again, if sending failed.
        Throws an exception if sending failed several times
        :param url: the backend service URL
        :param data: the data to send to the backend
        :param headers: the headers for the request
        :return: the response from the server
        """
        tries_left = 3
        while True:
            try:
                r = requests.post(url=url, data=data, headers=headers)
                return self._check_response(r)
            except Exception as e:
                # Try again if sending failed.
                tries_left -= 1
                if tries_left > 0:
                    if self.debug:
                        print("caught exception: {}. Retry... ({} attempt(s) left)\n".format(e, tries_left))
                    time.sleep(0.2)
                    continue
                else:
                    raise Exception("!! request to {} failed: {}".format(url, e))

    def _check_response(self, r: requests.Response) -> bytes:
        """
        Check the response of a http request to determine if sending was successful.
        Throws an exception if sending failed.
        :param r: the request response
        :return: the response content 
        """
        status = r.status_code
        if status == 200:
            if self.debug:
                print("** request successful\n")
            response = r.content
            r.close()
            return response
        else:
            message = r.text
            r.close()
            raise Exception("{}: {}".format(status, message))

    def register_identity(self, key_registration: bytes) -> bytes:
        """
        Register an identity at the key service.
        :param key_registration: the key registration data
        :return: the response from the server
        """
        if self.debug:
            print("** register identity at " + self.key_service_url.rstrip("/mpack"))
            print("** key registration message [json]: {}".format(key_registration.decode()))
        return self._send_request(url=self.key_service_url.rstrip("/mpack"),
                                  data=key_registration,
                                  headers={'Content-Type': 'application/json'})

    def send_upp(self, uuid: UUID, upp: bytes) -> bytes:
        """
        Send data to the authentication service. Requires encoding before sending.
        :param uuid: the sender's UUID
        :param upp: the msgpack encoded data to send (UPP)
        :return: the response from the server
        """
        if self.debug:
            print("** sending UPP to " + self.auth_service_url)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(url=self.auth_service_url,
                                  data=upp,
                                  headers=self._ubirch_headers)

    def send_data(self, uuid: UUID, message: bytes) -> bytes:
        """
        Send a message to the ubirch data service.
        :param uuid: the sender's UUID
        :param message: the message to send to the data service
        :return: the response from the server
        """
        if self.debug:
            print("** sending data message to " + self.data_service_url)
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(url=self.data_service_url,
                                  data=binascii.hexlify(message),
                                  headers=self._ubirch_headers)

    def verify(self, data: bytes, quick=False) -> bytes:
        """
        Verify a given hash at the verification service. Returns all available verification data.
        :param data: the message hash to verify
        :param quick: only run quick check to verify that the hash has been stored in backend
        :return: the response from the server (if the verification was successful and the data related to it)
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
        :return: the response from the server
        """
        if self.debug:
            print("** bootstrapping identity {} at {}".format(imsi, self.bootstrap_service_url))
        self._ubirch_headers['X-Ubirch-IMSI'] = imsi
        return requests.get(url=self.bootstrap_service_url, headers=self._ubirch_headers)
