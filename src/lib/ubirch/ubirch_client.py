import binascii
import json
import time

import ed25519

import logging
import umsgpack as msgpack
from uuid import UUID
from .ubirch_api import API
from .ubirch_ks import KeyStore
from .ubirch_protocol import Protocol, UBIRCH_PROTOCOL_TYPE_REG

logger = logging.getLogger(__name__)


class UbirchClient(Protocol):
    PUB_DEV = ed25519.VerifyingKey(
        b'\xa2\x40\x3b\x92\xbc\x9a\xdd\x36\x5b\x3c\xd1\x2f\xf1\x20\xd0\x20\x64\x7f\x84\xea\x69\x83\xf9\x8b\xc4\xc8\x7e\x0f\x4b\xe8\xcd\x66')  # public key for dev/demo stage
    PUB_PROD = ed25519.VerifyingKey(
        b'\xef\x80\x48\xad\x06\xc0\x28\x5a\xf0\x17\x70\x09\x38\x18\x30\xc4\x6c\xec\x02\x5d\x01\xd8\x60\x85\xe7\x5a\x4f\x00\x41\xc2\xe6\x90')  # public key for prod stage

    def __init__(self, uuid: UUID, cfg: dict):
        """
        Initialize the ubirch-protocol implementation and read existing
        key or generate a new key pair. Generating a new key pair requires
        the system time to be set or the certificate may be unusable.
        """
        super().__init__()

        self.uuid = uuid
        self.api = API(cfg)

        self.env = cfg["env"]

        # load existing key pair or generate new if there is none
        self._keystore = KeyStore(self.uuid)

        # after boot or restart try to register certificate
        cert = self._keystore.get_certificate()
        logger.debug("** key certificate : {}".format(json.dumps(cert)))

        key_registration = self.message_signed(self.uuid, UBIRCH_PROTOCOL_TYPE_REG, cert)
        logger.debug("** key registration message [msgpack]: {}".format(binascii.hexlify(key_registration).decode()))

        r = self.api.register_identity(key_registration)
        if r.status_code == 200:
            r.close()
            print(str(self.uuid) + ": identity registered\n")
        else:
            logger.error(str(self.uuid) + ": ERROR: device identity not registered")
            raise Exception("!! request to key service failed with status code {}: {}".format(r.status_code, r.text))

    def _sign(self, uuid: str, message: bytes) -> bytes:
        return self._keystore.get_signing_key().sign(message)

    def _verify(self, uuid: UUID, message: bytes, signature: bytes) -> bytes:
        if str(uuid) == str(self.uuid):
            return self._keystore.get_verifying_key().verify(signature, message)
        else:
            if self.env == "prod":
                return self.PUB_PROD.verify(signature, message)
            else:
                return self.PUB_DEV.verify(signature, message)

    def pack_data_message(self, data: dict) -> (bytes, bytes):
        """
        Generate a message for the ubirch data service.
        :param data: a map containing the data to be sent
        :return: a msgpack formatted array with the device UUID, message type, timestamp, data and hash
        :return: the hash of the data message
        """
        msg_type = 1

        msg = [
            self.uuid.bytes,
            msg_type,
            int(time.time()),
            data,
            0
        ]

        # calculate hash of message (without last array element)
        serialized = msgpack.packb(msg)[0:-1]
        message_hash = self._hash(serialized)

        # replace last element in array with the hash
        msg[-1] = message_hash
        serialized = msgpack.packb(msg)

        return serialized, message_hash

    def send(self, data: dict):
        """
        Send data message to ubirch data service. On success, send certificate of the message
        to ubirch authentication service.
        Throws exception if message couldn't be sent or response couldn't be verified.
        :param data: a map containing the data to be sent
        """
        # pack data message with measurements, device UUID, timestamp and hash of the message
        message, message_hash = self.pack_data_message(data)
        logger.debug("** data message [msgpack]: {}".format(binascii.hexlify(message).decode()))
        logger.debug("** hash: {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))

        # send data message to data service
        print("** sending measurements ...")
        r = self.api.send_data(self.uuid, message)
        if r.status_code == 200:
            print("** measurements successfully sent\n")
            r.close()
        else:
            raise Exception("!! request to data service failed with status code {}: {}".format(r.status_code, r.text))

        # create UPP with the data message hash
        upp = self.message_chained(self.uuid, 0x00, message_hash)
        logger.debug("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        #  send UPP to niomon
        print("** sending measurement certificate ...")
        r = self.api.send_upp(self.uuid, upp)
        if r.status_code == 200:
            print("hash: {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))
            print("** measurement certificate successfully sent\n")
            try:
                self.message_verify(r.content)
            except Exception as e:
                raise Exception("!! response verification failed: {}. {}".format(e, binascii.hexlify(r.content)))
        else:
            raise Exception(
                "!! request to authentication service failed with status code {}: {}".format(r.status_code, r.text))

        # verify that hash has been stored in backend
        print("** verifying ...")
        retries = 5
        while True:
            time.sleep(0.2)
            r = self.api.verify(message_hash, quick=True)
            if r.status_code == 200 or retries == 0:
                print("** verification successful: {}".format(r.text))
                break
            r.close()
            print("Hash could not be verified yet. Retry... ({} retires left)".format(retries))
            retries -= 1
