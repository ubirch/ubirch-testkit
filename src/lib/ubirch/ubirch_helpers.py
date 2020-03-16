import asn1
import machine
import os
import time
import ubinascii as binascii
import ujson as json
import umsgpack as msgpack
from uuid import UUID
from .ubirch_api import API
from .ubirch_sim import SimProtocol, APP_UBIRCH_SIGNED, APP_UBIRCH_CHAINED


def asn1tosig(data: bytes):
    s1 = asn1.asn1_node_root(data)
    a1 = asn1.asn1_node_first_child(data, s1)
    part1 = asn1.asn1_get_value(data, a1)
    a2 = asn1.asn1_node_next(data, a1)
    part2 = asn1.asn1_get_value(data, a2)
    if len(part1) > 32: part1 = part1[1:]
    if len(part2) > 32: part2 = part2[1:]
    return part1 + part2


def get_certificate(uuid: UUID, sim: SimProtocol, key_name: str) -> bytes:
    """
    Get a signed json with the key registration request until CSR handling is in place.
    TODO this will be replaced by the X.509 certificate from the SIM card
    """
    TIME_FMT = '{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.000Z'
    now = machine.RTC().now()
    created = not_before = TIME_FMT.format(now[0], now[1], now[2], now[3], now[4], now[5])
    later = time.localtime(time.mktime(now) + 30758400)
    not_after = TIME_FMT.format(later[0], later[1], later[2], later[3], later[4], later[5])
    pub_base64 = binascii.b2a_base64(sim.get_key(key_name)).decode()[:-1]
    # json must be compact and keys must be sorted alphabetically
    REG_TMPL = '{{"algorithm":"ecdsa-p256v1","created":"{}","hwDeviceId":"{}","pubKey":"{}","pubKeyId":"{}","validNotAfter":"{}","validNotBefore":"{}"}}'
    REG = REG_TMPL.format(created, str(uuid), pub_base64, pub_base64, not_after, not_before).encode()
    # get the ASN.1 encoded signature and extract the signature bytes from it
    signature = asn1tosig(sim.sign(key_name, REG, 0x00))
    return '{{"pubKeyInfo":{},"signature":"{}"}}'.format(REG.decode(),
                                                         binascii.b2a_base64(signature).decode()[:-1]).encode()


def get_pin(imsi: str, api: API) -> str:
    # load PIN or bootstrap if PIN unknown
    pin_file = imsi + ".bin"
    pin = ""
    if pin_file in os.listdir('.'):
        print("loading PIN for " + imsi + "\n")
        with open(pin_file, "rb") as f:
            pin = f.readline().decode()
    else:
        print("bootstrapping SIM identity " + imsi)
        r = api.bootstrap_sim_identity(imsi)
        if r.status_code == 200:
            info = json.loads(r.content)
            print("bootstrapping successful: " + repr(info) + "\n")
            pin = info['pin']
            with open(pin_file, "wb") as f:
                f.write(pin.encode())
        else:
            raise Exception("bootstrapping failed with status code {}: {}".format(r.status_code, r.text))
    return pin


def pack_data_msgpack(uuid: UUID, data: dict) -> bytes:
    """
    Generate a msgpack formatted message for the ubirch data service.
    The message contains the device UUID, timestamp and data to ensure unique hash.
    :param uuid: the device UUID
    :param data: the mapped data to be sent to the ubirch data service
    :return: the msgpack formatted message
    """
    # hint for the message format (version)
    MSG_TYPE = 1

    # pack the message
    msg = [
        uuid.bytes,
        MSG_TYPE,
        int(time.time()),
        data
    ]

    # return serialized message
    return msgpack.packb(msg)


def get_payload(upp: bytes) -> bytes:
    unpacked = msgpack.unpackb(upp)
    if unpacked[0] == APP_UBIRCH_SIGNED:
        return unpacked[3]
    elif unpacked[0] == APP_UBIRCH_CHAINED:
        return unpacked[4]
    else:
        raise Exception("!! can't get payload from {} (not a UPP)")
