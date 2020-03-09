import binascii
import json
import asn1
import machine
import os
import time
import urequests as requests
from network import LTE
from config import Config
from .ubirch_sim import SimProtocol


def asn1tosig(data: bytes):
    s1 = asn1.asn1_node_root(data)
    a1 = asn1.asn1_node_first_child(data, s1)
    part1 = asn1.asn1_get_value(data, a1)
    a2 = asn1.asn1_node_next(data, a1)
    part2 = asn1.asn1_get_value(data, a2)
    if len(part1) > 32: part1 = part1[1:]
    if len(part2) > 32: part2 = part2[1:]
    return part1 + part2


class UbirchSimClient(SimProtocol):

    def __init__(self, lte: LTE, cfg: Config):
        self.cfg = cfg
        self.key_name = "ukey"
        super().__init__(lte=lte, at_debug=cfg.debug)

        self._unlock_sim()

        self.uuid = self.get_uuid(self.key_name)
        print("** UUID   : " + str(self.uuid) + "\n")

    def _unlock_sim(self):
        # get IMSI from SIM
        imsi = self.get_imsi()
        print("** IMSI: " + imsi)
        # get pin to unlock SIM
        pin = self._get_pin(imsi)
        # use PIN to authenticate against the SIM application
        if not self.sim_auth(pin):
            raise Exception("PIN not accepted")

    def _get_pin(self, imsi) -> str:
        # load PIN or bootstrap if PIN unknown
        pin_file = imsi + ".bin"
        pin = ""
        if pin_file in os.listdir('.'):
            print("loading PIN for " + imsi)
            with open(pin_file, "rb") as f:
                pin = f.readline().decode()
        else:
            print("bootstrapping SIM identity " + imsi)
            r = self._bootstrap_sim_identity(imsi)
            if r.status_code == 200:
                info = json.loads(r.content)
                print("bootstrapping successful: " + info)
                pin = info['pin']
                with open(pin_file, "wb") as f:
                    f.write(pin.encode())
            else:
                raise Exception("bootstrapping failed with status code {}: {}".format(r.status_code, r.text))
        return pin

    def _bootstrap_sim_identity(self, imsi: str) -> requests.Response:
        """
        Claim SIM identity at the ubirch backend.
        The response contains the SIM applet PIN to unlock crypto functionality.
        :param imsi: the SIM international mobile subscriber identity (IMSI)
        :return: the response from the server
        """
        if self.cfg.debug: ("** bootstrapping identity {} at {}".format(imsi, self.cfg.boot))
        headers = {
            'X-Ubirch-IMSI': imsi,
            'X-Ubirch-Credential': binascii.b2a_base64(self.cfg.password).decode().rstrip('\n'),
            'X-Ubirch-Auth-Type': 'ubirch'
        }
        return requests.get(self.cfg.boot, headers=headers)

    def get_certificate(self, entry_id: str) -> bytes:
        """
        Get a signed json with the key registration request until CSR handling is in place.
        TODO this will be replaced by the X.509 certificate from the SIM card
        """
        TIME_FMT = '{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.000Z'
        now = machine.RTC().now()
        created = not_before = TIME_FMT.format(now[0], now[1], now[2], now[3], now[4], now[5])
        later = time.localtime(time.mktime(now) + 30758400)
        not_after = TIME_FMT.format(later[0], later[1], later[2], later[3], later[4], later[5])
        pub_base64 = binascii.b2a_base64(self.get_key(self.key_name)).decode()[:-1]
        # json must be compact and keys must be sorted alphabetically
        REG_TMPL = '{{"algorithm":"ecdsa-p256v1","created":"{}","hwDeviceId":"{}","pubKey":"{}","pubKeyId":"{}","validNotAfter":"{}","validNotBefore":"{}"}}'
        REG = REG_TMPL.format(created, str(self.uuid), pub_base64, pub_base64, not_after, not_before).encode()
        # get the ASN.1 encoded signature and extract the signature bytes from it
        signature = asn1tosig(self.sign(self.key_name, REG, 0x00))
        return '{{"pubKeyInfo":{},"signature":"{}"}}'.format(REG.decode(),
                                                             binascii.b2a_base64(signature).decode()[:-1]).encode()
