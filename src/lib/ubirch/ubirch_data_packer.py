import time
import umsgpack as msgpack
from uuid import UUID
from hashlib import sha512

# hint for the message format (version)
MSG_TYPE = 1


def pack_data_msgpack(uuid: UUID, data: dict) -> (bytes, bytes):
    """
    Generate a msgpack formatted message for the ubirch data service.
    The message contains the device UUID, timestamp and data to ensure unique hash.
    The sha512 hash of the message will be appended to the message.
    :param uuid: the device UUID
    :param data: the mapped data to be sent to the ubirch data service
    :return: the msgpack formatted message, the hash of the data message
    """
    msg = [
        uuid.bytes,
        MSG_TYPE,
        int(time.time()),
        data,
        0
    ]

    # calculate hash of message (without last array element)
    serialized = msgpack.packb(msg)[0:-1]
    message_hash = sha512(serialized).digest()

    # replace last element in array with the hash
    msg[-1] = message_hash
    serialized = msgpack.packb(msg)

    return serialized, message_hash
