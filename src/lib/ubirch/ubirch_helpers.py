import os
import time

from uuid import UUID
from .ubirch_api import API


def bootstrap(imsi: str, api: API) -> str:
    """
    Load PIN or bootstrap if PIN unknown
    """
    pin_file = imsi + ".bin"
    if pin_file in os.listdir():
        print("loading PIN for " + imsi + "\n")
        with open(pin_file, "rb") as f:
            return f.readline().decode()
    else:
        print("bootstrapping SIM identity " + imsi)
        from connection import get_connection
        c = get_connection(None, {})
        c.connect()
        r = api.bootstrap_sim_identity(imsi)
        c.disconnect()
        if not 200 <= r.status_code < 300:
            raise Exception("bootstrapping failed: ({}) {}".format(r.status_code, str(r.content)))

        from json import loads
        info = loads(r.content)
        pin = info['pin']

        # sanity check
        try:
            if len(pin) != 4: raise ValueError("len = {}".format(len(pin)))
            int(pin)  # throws ValueError if pin has invalid syntax for integer with base 10
        except ValueError as e:
            raise Exception("bootstrapping returned invalid PIN: ".format(e))

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
        from binascii import hexlify
        raise Exception("!! can't get payload from {} (not a UPP)".format(hexlify(upp).decode()))

    if upp[payload_start_idx - 2] != 0xC4:
        raise Exception("unexpected payload type: %X".format(upp[payload_start_idx - 2]))

    payload_len = upp[payload_start_idx - 1]
    return upp[payload_start_idx:payload_start_idx + payload_len]
