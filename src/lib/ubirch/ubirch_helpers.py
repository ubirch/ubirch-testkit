import os
import time
import ubinascii as binascii
import ujson as json
from uuid import UUID
from .ubirch_api import API
from .ubirch_sim import SimProtocol


def bootstrap(imsi: str, api: API) -> str:
    """
    Load PIN or bootstrap if PIN unknown
    """
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
            if info['encrypted']:  # not implemented yet
                # decrypt PIN here
                pass
            else:
                pin = info['pin']

            with open(pin_file, "wb") as f:
                f.write(pin.encode())
        else:
            raise Exception("bootstrapping failed with status code {}: {}".format(r.status_code, r.text))
    return pin


def submit_csr(uuid: UUID, key_name: str, sim: SimProtocol, api: API):
    """
    Submit a X.509 Certificate Signing Request
    """
    csr_file = "csr_{}_{}.der".format(str(uuid), api.env)
    if csr_file not in os.listdir():
        print("** submitting CSR to identity service ...")
        csr = sim.generate_csr(key_name)
        api.send_csr(csr)
        with open(csr_file, "wb") as f:
            f.write(csr)


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

    if upp[payload_start_idx - 2] != 0xC4:
        raise Exception("unexpected payload type: %X".format(upp[payload_start_idx - 2]))

    payload_len = upp[payload_start_idx - 1]
    return upp[payload_start_idx:payload_start_idx + payload_len]
