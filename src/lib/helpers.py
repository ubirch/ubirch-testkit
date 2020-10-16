import machine
import os
import time

from connection import Connection
from modem import reset_modem
from network import LTE
from uuid import UUID

import ubirch


def mount_sd():
    try:
        sd = machine.SD()
        try:#check if sd is already mounted
            os.stat('/sd')
            return True
        except:#not mounted: continue
            pass
        os.mount(sd, '/sd')
        return True
    except OSError:
        return False


def store_imsi(imsi: str):
    # save imsi to file on SD, SD needs to be mounted
    imsi_file = "imsi.txt"
    if imsi_file not in os.listdir('/sd'):
        print("\twriting IMSI to SD")
        with open('/sd/' + imsi_file, 'w') as f:
            f.write(imsi)


def get_pin_from_flash(pin_file: str, imsi: str) -> str or None:
    if pin_file in os.listdir():
        print("\tloading PIN for " + imsi)
        with open(pin_file, "rb") as f:
            return f.readline().decode()
    else:
        print("\tno PIN found for " + imsi)
        return None


def send_backend_data(sim: ubirch.SimProtocol, lte: LTE, conn: Connection, api_function, uuid, data) -> (int, bytes):
    MAX_MODEM_RESETS = 1  # number of retries with modem reset before giving up
    MAX_RECONNECTS = 1  # number of retries with reconnect before trying a modem reset

    for reset_attempts in range(MAX_MODEM_RESETS + 1):
        # check if this is a retry for reset_attempts
        if reset_attempts > 0:
            print("\tretrying with modem reset")
            sim.deinit()
            reset_modem(lte)  # TODO: should probably be connection.reset_hardware()
            conn.connect()

        # try to send multiple times (with reconnect)
        try:
            for send_attempts in range(MAX_RECONNECTS + 1):
                # check if this is a retry for send_attempts
                if send_attempts > 0:
                    print("\tretrying with disconnect/reconnect")
                    conn.disconnect()
                    conn.connect()
                try:
                    print("\tsending...")
                    return api_function(uuid, data)
                except Exception as e:
                    # TODO: log/print exception?
                    print("\tsending failed: {}".format(e))
                    # (continues to top of send_attempts loop)
            else:
                # all send attempts used up
                raise Exception("all send attempts failed")
        except Exception as e:
            print(repr(e))
            # (continues to top of reset_attempts loop)
    else:
        # all modem resets used up
        raise Exception("could not establish connection to backend")


def bootstrap(imsi: str, api: ubirch.API) -> str:
    """
    Load bootstrap PIN, returns PIN
    """
    print("\tbootstrapping SIM identity " + imsi)
    status_code, content = api.bootstrap_sim_identity(imsi)
    if not 200 <= status_code < 300:
        raise Exception("bootstrapping failed: ({}) {}".format(status_code, str(content)))

    from json import loads
    info = loads(content)
    pin = info['pin']

    # sanity check
    try:
        if len(pin) != 4: raise ValueError("len = {}".format(len(pin)))
        int(pin)  # throws ValueError if pin has invalid syntax for integer with base 10
    except ValueError as e:
        raise Exception("bootstrapping returned invalid PIN: ".format(e))

    return pin


def submit_csr(key_name: str, csr_country: str, csr_organization: str, sim: ubirch.SimProtocol,
               api: ubirch.API) -> bytes:
    """
    Submit a X.509 Certificate Signing Request. Returns CSR in der format.
    """
    print("** submitting CSR to identity service ...")
    csr = sim.generate_csr(key_name, csr_country, csr_organization)
    status_code, content = api.send_csr(csr)
    if not 200 <= status_code < 300:
        raise Exception("submitting CSR failed: ({}) {}".format(status_code, str(content)))
    return csr


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


def pack_data_hash_json(uuid: UUID, data: dict, _hash: str) -> bytes:
    """
    Generate a JSON formatted message for the ubirch data service.
    The message contains the device UUID, timestamp and data to ensure unique hash.
    :param uuid: the device UUID
    :param data: the mapped data to be sent to the ubirch data service
    :param _hash: this is a temporary hashing solution for verification. TODO has to be removed later
    :return: the msgpack formatted message
    """
    # hint for the message format (version)
    MSG_TYPE = 1

    # pack the message
    msg_map = {
        'uuid': str(uuid),
        'msg_type': MSG_TYPE,
        'timestamp': int(time.time()),
        'data': data,
        'hash': _hash
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
