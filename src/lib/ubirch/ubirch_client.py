import binascii
import ed25519
import json
import logging
import time
import umsgpack as msgpack
from uuid import UUID
from .ubirch_api import API
from .ubirch_ks import KeyStore
from .ubirch_protocol import Protocol, UBIRCH_PROTOCOL_TYPE_REG

logger = logging.getLogger(__name__)


class UbirchClient(Protocol):
    UUID_DEV = UUID(binascii.unhexlify("9d3c78ff22f34441a5d185c636d486ff"))  # UUID of dev/demo stage
    UUID_PROD = UUID(binascii.unhexlify("10b2e1a456b34fff9adacc8c20f93016"))  # UUID of prod stage
    PUB_DEV = ed25519.VerifyingKey(binascii.unhexlify(
        "a2403b92bc9add365b3cd12ff120d020647f84ea6983f98bc4c87e0f4be8cd66"))  # public key for dev/demo stage
    PUB_PROD = ed25519.VerifyingKey(binascii.unhexlify(
        "ef8048ad06c0285af0177009381830c46cec025d01d86085e75a4f0041c2e690"))  # public key for prod stage

    def __init__(self, uuid: UUID, cfg: dict):
        """
        Initialize the ubirch-protocol implementation and read existing
        key or generate a new key pair. Generating a new key pair requires
        the system time to be set or the certificate may be unusable.
        """
        super().__init__()

        self.uuid = uuid
        self.api = API(cfg)

        # load existing key pair or generate new if there is none
        self._keystore = KeyStore(self.uuid)

        # store backend public keys in keystore
        self._keystore.insert_verifying_key(self.UUID_DEV, self.PUB_DEV)
        self._keystore.insert_verifying_key(self.UUID_PROD, self.PUB_PROD)

        # after boot or restart try to register certificate
        cert = self._keystore.get_certificate()
        logger.debug("** key certificate : {}".format(json.dumps(cert)))

        key_registration = self.message_signed(self.uuid, UBIRCH_PROTOCOL_TYPE_REG, cert)
        logger.debug("** key registration message [msgpack]: {}".format(binascii.hexlify(key_registration).decode()))

        # send key registration message to key service
        print("** registering identity at key service ...")
        r = self.api.register_identity(key_registration)
        r.close()
        print("** identity registered\n")

    def _sign(self, uuid: UUID, message: bytes) -> bytes:
        return self._keystore.get_signing_key().sign(message)

    def _verify(self, uuid: UUID, message: bytes, signature: bytes) -> bytes:
        return self._keystore.get_verifying_key(uuid).verify(signature, message)

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
        Send data message to ubirch data service and certificate of the message to ubirch authentication service.
        Throws exception if sending message failed  or response from backend couldn't be verified.
        :param data: data map to to be sent
        """
        # pack data message containing measurements, device UUID and timestamp to ensure unique hash
        message, message_hash = self.pack_data_message(data)
        logger.debug("** data message [msgpack]: {}".format(binascii.hexlify(message).decode()))
        logger.debug("** message hash [base64] : {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))

        # send message to data service
        print("** sending measurements ...")
        r = self.api.send_data(self.uuid, message)
        r.close()
        print("** measurements successfully sent\n")

        # create UPP with the data message hash
        upp = self.message_chained(self.uuid, 0x00, message_hash)
        logger.debug("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        #  send UPP to authentication service
        print("** sending measurement certificate ...")
        r = self.api.send_upp(self.uuid, upp)
        print("hash: {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))
        print("** measurement certificate successfully sent\n")

        # verify response from server
        response_content = r.content
        try:
            logger.debug("** verifying response from {}: {}".format(self.api.auth_service_url,
                                                                    binascii.hexlify(response_content)))
            self.message_verify(response_content)
            logger.debug("** response verified\n")
        except Exception as e:
            raise Exception(
                "!! response verification failed: {}. {} ".format(e, binascii.hexlify(response_content)))

        # verify that hash has been stored and chained in backend
        print("** verifying hash in backend ...")
        tries_left = 4
        while True:
            tries_left -= 1
            time.sleep(0.5)
            try:
                r = self.api.verify(message_hash)
                print("** backend verification successful: {}".format(r.text))
                break
            except Exception as e:
                if tries_left > 0:
                    print("Hash could not be verified yet. Retry... ({} attempt(s) left)".format(tries_left))
                else:
                    raise Exception("!! backend verification failed. {}".format(e))
