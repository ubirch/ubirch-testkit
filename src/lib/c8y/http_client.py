import os
import ujson as json
import time
from uuid import UUID
from binascii import b2a_base64

import urequests as requests
from urequests import Response

class C8yHTTPClient(object):
    DEBUG = False

    def __init__(self, uuid: UUID, bootstrap: dict, device_info: dict) -> None:
        super().__init__()
        self._C8Y_HOST = "https://{}.cumulocity.com".format(bootstrap["tenant"])

        serial = str(uuid)
        credentials_file = "{}.ini".format(uuid)
        self._credentials = None
        if credentials_file in os.listdir():
            try:
                with open(credentials_file, "r") as f:
                    self._credentials = json.loads(f.read())
            except Exception as e:
                print("unable to load credentials: {}".format(e))

        if not self._credentials:
            print("device has no credentials yet, bootstrapping: {}".format(serial))
            self._credentials = self.bootstrap(serial, bootstrap)
            with open(credentials_file, "w+") as f:
                f.write(json.dumps(self._credentials))
        self._auth = b'Basic '+b2a_base64(b':'.join((
            self._credentials["username"].encode(),
            self._credentials["password"].encode()
        ))).strip()

        self._id = self.registered(serial)
        if self._id is None:
            self._id = self.create(device_info)
            self.register(serial, self._id)

        print("serial={}, id={}".format(serial, self._id))

    def bootstrap(self, serial, bootstrap: dict) -> dict:
        credentials = None
        while credentials is None:
            tenant = bootstrap["tenant"]
            host = bootstrap["host"]
            authorization = bootstrap["authorization"]
            r = requests.post("https://" + host + "/devicecontrol/deviceCredentials",
                              headers={
                                  'Authorization': authorization,
                                  'Content-Type': 'application/vnd.com.nsn.cumulocity.deviceCredentials+json',
                                  'Accept': 'application/vnd.com.nsn.cumulocity.deviceCredentials+json'
                              },
                              json={"id": serial})
            if self.DEBUG: print("{}: {}".format(r.status_code, bytes.decode(r.content)))
            if 200 < r.status_code < 300:
                return r.json()
            time.sleep(10)

    def registered(self, serial: str) -> str or None:
        r = requests.get(self._C8Y_HOST + "/identity/externalIds/c8y_Serial/{}".format(serial),
                         headers={
                             "Authorization": self._auth,
                             "Accept": "application/vnd.com.nsn.cumulocity.externalId+json"
                         })
        if self.DEBUG: print("{}: {}".format(r.status_code, bytes.decode(r.content)))
        if r.status_code == 200 and 'managedObject' in r.json():
            return r.json()["managedObject"]["id"]

        return None

    def create(self, device_info: dict) -> str:
        r = requests.post(self._C8Y_HOST + "/inventory/managedObjects",
                          headers={
                              'Authorization': self._auth,
                              'Content-Type': 'application/vnd.com.nsn.cumulocity.managedObject+json',
                              'Accept': 'application/vnd.com.nsn.cumulocity.managedObject+json'
                          },
                          json=device_info)
        if self.DEBUG: print("{}: {}".format(r.status_code, bytes.decode(r.content)))
        if r.status_code == 201:
            return r.json()["id"]
        r.raise_for_status()

    def register(self, serial: str, id: str) -> bool:
        r = requests.post(self._C8Y_HOST + "/identity/globalIds/{}/externalIds".format(id),
                          headers={
                              'Authorization': self._auth,
                              'Content-Type': 'application/vnd.com.nsn.cumulocity.externalId+json',
                              'Accept': 'application/vnd.com.nsn.cumulocity.externalId+json'
                          },
                          json={"type": "c8y_Serial", "externalId": serial})
        if self.DEBUG: print("{}: {}".format(r.status_code, bytes.decode(r.content)))
        return r.status_code == 201

    def measurement(self, data: dict) -> Response:
        data["source"] = {'id': self._id}
        r = requests.post(self._C8Y_HOST + "/measurement/measurements",
                          headers={
                              'Authorization': self._auth,
                              'Content-Type': 'application/vnd.com.nsn.cumulocity.measurement+json',
                              'Accept': 'application/vnd.com.nsn.cumulocity.measurement+json'
                          },
                          json=data)
        if self.DEBUG: print("{}: {}".format(r.status_code, bytes.decode(r.content)))
        if r.status_code == 201:
            return r.json()
        r.raise_for_status()

    def alarm(self, data: dict) -> Response:
        data["source"] = {'id': self._id}
        r = requests.post(self._C8Y_HOST + "/alarm/alarms",
                          headers={
                              'Authorization': self._auth,
                              'Content-Type': 'application/vnd.com.nsn.cumulocity.alarm+json',
                              'Accept': 'application/vnd.com.nsn.cumulocity.alarm+json'
                          },
                          json=data)
        if self.DEBUG: print("{}: {}".format(r.status_code, bytes.decode(r.content)))
        if r.status_code == 201:
            return r.json()
        r.raise_for_status()
