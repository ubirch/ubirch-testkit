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

        r = self.api.register_identity(key_registration)
        if r.status_code == 200:
            r.close()
            print(str(self.uuid) + ": identity registered\n")
        else:
            logger.error(str(self.uuid) + ": ERROR: device identity not registered")
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.key_service_url, r.status_code,
                                                                         r.text))

    def _sign(self, uuid: str, message: bytes) -> bytes:
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
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.data_service_url, r.status_code,
                                                                         r.text))

        # create UPP with the data message hash
        upp = self.message_chained(self.uuid, 0x00, message_hash)
        logger.debug("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        #  send UPP to authentication service
        print("** sending measurement certificate ...")
        r = self.api.send_upp(self.uuid, upp)
        if r.status_code == 200:
            print("hash: {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))
            print("** measurement certificate successfully sent\n")
            response_content = r.content
            try:
                logger.debug("** verifying response from {}: {}".format(self.api.auth_service_url, binascii.hexlify(response_content)))
                self.message_verify(response_content)
                logger.debug("** response verified")
            except Exception as e:
                raise Exception(
                    "!! response verification failed: {}. {} ".format(e, binascii.hexlify(response_content)))
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.auth_service_url, r.status_code,
                                                                         r.text))

        # # verify that hash has been stored in backend
        # print("** verifying hash in backend ...")
        # retries = 5
        # while True:
        #     time.sleep(0.2)
        #     r = self.api.verify(message_hash)
        #     if r.status_code == 200:
        #         print("** backend verification successful: {}".format(r.text))
        #         break
        #     if retries == 0:
        #         raise Exception("!! backend verification ({}) failed with status code {}: {}".format(self.api.verification_service_url, r.status_code, r.text))
        #     r.close()
        #     print("Hash could not be verified yet. Retry... ({} retires left)".format(retries))
        #     retries -= 1
