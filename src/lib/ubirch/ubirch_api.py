import time
import ubinascii as binascii
import urequests as requests
from uuid import UUID


class API:
    """ubirch API accessor methods."""

    def __init__(self, cfg: dict):
        self.debug = cfg['debug']
        self.env = cfg['env']
        self.data_service_url = cfg['data']
        self.auth_service_url = cfg['niomon']
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
        err = ""
        for _ in range(3):
            try:
                r = requests.post(url=url, data=data, headers=headers)
                return self._check_response(r)
            except Exception as e:
                # Try again if sending failed.
                err = str(e)
                if self.debug: print("!! sending request failed: {}\n".format(err))
                time.sleep(0.5)

        raise Exception("!! request to {} failed: {}".format(url, err))

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
            message = r.content
            r.close()
            raise Exception("({}) {}".format(status, message))

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
        Send a json formatted data message to the ubirch data service.
        :param uuid: the sender's UUID
        :param message: the json formatted message to send to the data service
        :return: the response from the server
        """
        if self.debug:
            print("** sending data message to " + self.data_service_url + "/json")
        self._ubirch_headers['X-Ubirch-Hardware-Id'] = str(uuid)
        return self._send_request(url=self.data_service_url + "/json",
                                  data=message,
                                  headers=self._ubirch_headers)

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
