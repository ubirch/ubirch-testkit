import asn1
import machine
import os
import time
import ubinascii as binascii
import ujson as json
from uuid import UUID
from .ubirch_api import API
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


def get_certificate(uuid: UUID, sim: SimProtocol, key_name: str) -> bytes:
    """
    Load or create new key certificate. The created certificates are stored in a binary file in the flash memory.
    TODO this will be replaced by the X.509 certificate from the SIM card
    """
    cert_file = str(uuid) + "_crt.bin"
    if cert_file in os.listdir():
        print("** loading existing key certificate for identity " + str(uuid))
        with open(cert_file, "rb") as cf:
            return cf.read()
    else:
        print("** generating new key certificate for identity " + str(uuid))
        cert = _create_certificate(uuid, sim, key_name)
        with open(cert_file, "wb") as cf:
            cf.write(cert)


def _create_certificate(uuid: UUID, sim: SimProtocol, key_name: str) -> bytes:
    """
    Get a signed json with the key registration request until CSR handling is in place.
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
    if pin_file in os.listdir():
        print("loading PIN for " + imsi + "\n")
        with open(pin_file, "rb") as f:
            pin = f.readline().decode()
    else:
        print("bootstrapping SIM identity " + imsi)
        r = api.bootstrap_sim_identity(imsi)
        if r.status_code == 200:
            info = json.loads(r.content)
            print("bootstrapping successful\n")
            pin = info['pin']
            with open(pin_file, "wb") as f:
                f.write(pin.encode())
        else:
            raise Exception("bootstrapping failed with status code {}: {}".format(r.status_code, r.text))
    return pin


def pack_data_json(uuid: UUID, data: dict) -> bytes:
    """
    Generate a JSON formatted message for the ubirch data service.
    The message contains the device UUID, timestamp and data to ensure unique hash.
    :param uuid: the device UUID
    :param data: the mapped data to be sent to the ubirch data service
    :return: the msgpack formatted message
    """
    # hint for the message format (version)
    MSG_TYPE = 1

    # pack the message
    msg_map = {
        'uuid': str(uuid),
        'msg_type': MSG_TYPE,
        'timestamp': int(time.time()),
        'data': data
    }

    # create a compact sorted rendering of the message to ensure determinism when creating the hash
    # and return serialized message
    return serialize_json(msg_map)


def serialize_json(msg: dict) -> bytes:
    """
    create a compact sorted rendering of a json object since micropython
    implementation of ujson.dumps does not support sorted keys
    :param msg: the json object (dict) to serialize
    :return: the compact sorted rendering
    """
    serialized = "{"
    for key in sorted(msg):
        serialized += "\"{}\":".format(key)
        value = msg[key]
        value_type = type(value)
        if value_type is str:
            serialized += "\"{:s}\"".format(value)
        elif value_type is int:
            serialized += "{:d}".format(value)
        elif isinstance(value, float):
            serialized += "\"{:.2f}\"".format(value)
        elif value_type is dict:
            serialized += serialize_json(value).decode()
        else:
            raise Exception("unsupported data type {} for serialization in json message".format(value_type))
        serialized += ","
    serialized = serialized.rstrip(",") + "}"  # replace last comma with closing braces
    return serialized.encode()


def get_upp_payload(upp: bytes) -> bytes:
    """
    Get the payload of a Ubirch Protocol Message
    """
    if upp[0] == 0x95 and upp[1] == 0x22:  # signed UPP
        payload_start_idx = 23
    elif upp[0] == 0x96 and upp[1] == 0x23:  # chained UPP
        payload_start_idx = 89
    else:
        raise Exception("!! can't get payload from {} (not a UPP)".format(binascii.hexlify(upp).decode()))

    payload_len = upp[payload_start_idx - 1]
    return upp[payload_start_idx:payload_start_idx + payload_len]
