# ubirch protocol
#
# Copyright (c) 2018 ubirch GmbH.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import hashlib
import umsgpack as msgpack
from uuid import UUID

logger = lambda msg: print(__name__+"{}".format(msg))

# ubirch-protocol constants
UBIRCH_PROTOCOL_VERSION = 2

PLAIN = ((UBIRCH_PROTOCOL_VERSION << 4) | 0x01)
SIGNED = ((UBIRCH_PROTOCOL_VERSION << 4) | 0x02)
CHAINED = ((UBIRCH_PROTOCOL_VERSION << 4) | 0x03)

UBIRCH_PROTOCOL_TYPE_BIN = 0x00
UBIRCH_PROTOCOL_TYPE_REG = 0x01
UBIRCH_PROTOCOL_TYPE_HSK = 0x02


class Protocol(object):
    _signatures = {}

    def __init__(self, names: dict, signatures: dict = None) -> None:
        """
        Initialize the protocol.
        :param signatures: previously known signatures
        """
        if signatures is None:
            signatures = {}
        self._signatures = signatures
        self._names = names

    def set_saved_signatures(self, signatures: dict) -> None:
        """
        Set known signatures from devices we have talked to.
        :param signatures: the saved signatures as a dictionary (uuid -> bytes)
        """
        self._signatures = signatures

    def get_saved_signatures(self) -> dict:
        """
        Get the saved signatures to store them persistently.
        :return: a dictionary of signatures (uuid -> bytes)
        """
        return self._signatures

    def reset_signature(self, uuid: UUID) -> None:
        """
        Reset the last saved signature for this UUID.
        :param uuid: the UUID to reset
        """
        if uuid in self._signatures:
            del self._signatures[uuid]

    def _hash(self, message: bytes) -> bytes:
        """
        Hash the message before signing. Override this method if
        a different hash algorithm is used. Default is SHA512.
        :param message: the message bytes
        :return: the digest in bytes
        """
        return hashlib.sha512(message).digest()

    def _sign(self, uuid: UUID, message: bytes) -> bytes:
        """
        Sign the request when finished.
        :param uuid: the uuid of the sender to identify the correct key pair
        :param message: the bytes to sign
        :return: the signature
        """
        raise NotImplementedError("signing not implemented")

    def _verify(self, uuid: UUID, message: bytes, signature: bytes):
        """
        Verify the message. Throws exception if not verifiable.
        :param uuid: the uuid of the sender to identify the correct key pair
        :param message: the message bytes to verify
        :param signature: the signature to use for verification
        :return:
        """
        raise NotImplementedError("verification not implemented")

    def _serialize(self, msg: any) -> bytearray:
        return bytearray(msgpack.packb(msg))

    def _prepare_and_sign(self, uuid: UUID, msg: any) -> (bytes, bytes):
        """
        Sign the request when finished. The message is first prepared by serializing and hashing it.
        :param uuid: the uuid of the sender to identify the correct key pair
        :param msg: the bytes to sign
        :return: the signature
        """
        # sign the message and store the signature
        serialized = self._serialize(msg)[0:-1]
        signature = self._sign(uuid, self._hash(serialized))
        # replace last element in array with the signature
        msg[-1] = signature
        return signature, self._serialize(msg)

    def message_signed(self, name: str, payload: any, type: int = UBIRCH_PROTOCOL_TYPE_BIN,
                       save_signature: bool = False) -> bytes:
        """
        Create a new signed ubirch-protocol message.
        :param name: the device name linked to the uuid of the device that sends the message
        :param payload: the actual message payload
        :param type: a hint of the type of message sent (0-255)
        :param save_signature: save the signature of the created message so the next chained message contains it
        :return: the encoded and signed message
        """
        uuid = self._names[name]
        msg = [
            SIGNED,
            uuid.bytes,
            type,
            payload,
            0
        ]

        (signature, serialized) = self._prepare_and_sign(uuid, msg)
        if save_signature:
            self._signatures[uuid] = signature

        # serialize result and return the message
        return serialized

    def message_chained(self, name: str, payload: any, type: int = UBIRCH_PROTOCOL_TYPE_BIN) -> bytes:
        """
        Create a new chained ubirch-protocol message.
        Stores the context, the last signature, to be included in the next message.
        :param name: the device name linked to the uuid of the device that sends the message
        :param payload: the actual message payload
        :param type: a hint of the type of message sent (0-255)
        :return: the encoded and chained message
        """
        uuid = self._names[name]

        # retrieve last known signature or null bytes
        last_signature = self._signatures.get(uuid, b'\0' * 64)

        msg = [
            CHAINED,
            uuid.bytes,
            last_signature,
            type,
            payload,
            0
        ]

        (signature, serialized) = self._prepare_and_sign(uuid, msg)
        self._signatures[uuid] = signature

        # serialize result and return the message
        return serialized

    def _prepare_and_verify(self, uuid: UUID, message: bytes, signature: bytes) -> bytes:
        """
        Verify the message. Throws exception if not verifiable. The message is first prepared by hashing it.
        :param uuid: the uuid of the sender to identify the correct key pair
        :param message: the message bytes to verify
        :param signature: the signature to use for verification
        :return:
        """
        return self._verify(uuid, self._hash(message), signature)

    def message_verify(self, name: str, message: bytes) -> bool:
        """
        Verify the integrity of a ubirch message.
        Throws an exception if the message is not verifiable.
        :param message: the msgpack encoded message
        :return: whether the message can be verified
        """
        min_len = 88
        if len(message) < min_len:
            raise Exception("wrong message format (size < {} bytes): {}".format(min_len, len(message)))

        unpacked = msgpack.unpackb(message)
        uuid = UUID(unpacked[1])
        if unpacked[0] == SIGNED:
            signature = unpacked[4]
        else:
            signature = unpacked[5]

        try:
            self._prepare_and_verify(uuid, message[0:-66], signature)
            return True
        except ValueError:
            return False
