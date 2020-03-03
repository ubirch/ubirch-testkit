import binascii

import asn1
import machine
import os
import time
from network import LTE
from uuid import UUID
from .ubirch_sim import SimProtocol
from .ubirch_api import API


def asn1tosig(data: bytes):
    s1 = asn1.asn1_node_root(data)
    a1 = asn1.asn1_node_first_child(data, s1)
    part1 = asn1.asn1_get_value(data, a1)
    a2 = asn1.asn1_node_next(data, a1)
    part2 = asn1.asn1_get_value(data, a2)
    if len(part1) > 32: part1 = part1[1:]
    if len(part2) > 32: part2 = part2[1:]
    return part1 + part2


def get_certificate(device_id: str, device_uuid: UUID, proto: SimProtocol) -> str:
    """
    Get a signed json with the key registration request until CSR handling is in place.
    """
    # TODO fix handling of key validity (will be fixed by handling CSR generation through SIM card)
    TIME_FMT = '{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.000Z'
    now = machine.RTC().now()
    created = not_before = TIME_FMT.format(now[0], now[1], now[2], now[3], now[4], now[5])
    later = time.localtime(time.mktime(now) + 30758400)
    not_after = TIME_FMT.format(later[0], later[1], later[2], later[3], later[4], later[5])
    pub_base64 = binascii.b2a_base64(proto.get_key(device_id)).decode()[:-1]
    # json must be compact and keys must be sorted alphabetically
    REG_TMPL = '{{"algorithm":"ecdsa-p256v1","created":"{}","hwDeviceId":"{}","pubKey":"{}","pubKeyId":"{}","validNotAfter":"{}","validNotBefore":"{}"}}'
    REG = REG_TMPL.format(created, str(device_uuid), pub_base64, pub_base64, not_after, not_before).encode()
    # get the ASN.1 encoded signature and extract the signature bytes from it
    signature = asn1tosig(proto.sign(device_id, REG, 0x00))
    return '{{"pubKeyInfo":{},"signature":"{}"}}'.format(REG.decode(), binascii.b2a_base64(signature).decode()[:-1])


class UbirchSimClient:

    def __init__(self, name: str, cfg: dict, lte: LTE):

        # initialize the ubirch protocol interface and backend API
        self.ubirch = SimProtocol(lte=lte, at_debug=cfg['debug'])
        cfg['keyService'] = str(cfg['keyService']).rstrip("/mpack")
        self.api = API(cfg)

        # get IMSI from SIM
        imsi = self.ubirch.get_imsi()
        print("IMSI: " + imsi)

        # load PIN or bootstrap if PIN unknown
        pin_file = imsi + ".bin"
        pin = ""
        if pin_file in os.listdir('.'):
            print("loading PIN for " + imsi)
            with open(pin_file, "rb") as f:
                pin = f.readline().decode()
        else:
            print("bootstrapping SIM identity" + imsi)
            pin = self.api.bootstrap_service_url(imsi)
            with open(pin_file, "wb") as f:
                f.write(pin.encode())

        # use PIN to authenticate against the SIM application
        if not self.ubirch.sim_auth(pin):
            raise Exception("PIN not accepted")

        # get UUID from SIM
        device_uuid = self.ubirch.get_uuid(name)

        # create a certificate for the device and register public key at ubirch key service
        # todo this will be replaced by the X.509 certificate from the SIM card
        cert = get_certificate(name, device_uuid, self.ubirch)

        # send certificate to key service
        print("** registering identity at key service ...")
        r = self.api.register_identity(cert.encode())
        r.close()
        print("** identity registered\n")