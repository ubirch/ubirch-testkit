import binascii
import ed25519
import json
import logging
import time
from config import Config
from uuid import UUID
from .ubirch_data_packer import pack_data_msgpack
from .ubirch_api import API
from .ubirch_ks import KeyStore
from .ubirch_protocol import Protocol, UBIRCH_PROTOCOL_TYPE_REG

logger = logging.getLogger(__name__)


class ProtoImpl(Protocol):

    def __init__(self, keystore: KeyStore, signatures: dict = None):
        self._keystore = keystore
        super().__init__(self._keystore.names, signatures)

    def _sign(self, uuid: UUID, message: bytes) -> bytes:
        return self._keystore.get_signing_key(uuid).sign(message)

    def _verify(self, uuid: UUID, message: bytes, signature: bytes) -> bytes:
        return self._keystore.get_verifying_key(uuid).verify(signature, message)


class UbirchProtocolClient:
    UUID_DEMO = UUID(binascii.unhexlify("9d3c78ff22f34441a5d185c636d486ff"))  # UUID of dev/demo stage
    UUID_PROD = UUID(binascii.unhexlify("10b2e1a456b34fff9adacc8c20f93016"))  # UUID of prod stage
    PUB_DEMO = ed25519.VerifyingKey(binascii.unhexlify(
        "a2403b92bc9add365b3cd12ff120d020647f84ea6983f98bc4c87e0f4be8cd66"))  # public key for dev/demo stage
    PUB_PROD = ed25519.VerifyingKey(binascii.unhexlify(
        "ef8048ad06c0285af0177009381830c46cec025d01d86085e75a4f0041c2e690"))  # public key for prod stage

    def __init__(self, cfg: Config, uuid: UUID):
        """
        Initialize the ubirch-protocol implementation and read existing
        key or generate a new key pair. Generating a new key pair requires
        the system time to be set or the certificate may be unusable.
        """
        self.device_name = "A"
        self.uuid = uuid
        self.api = API(cfg)

        # load existing key pair or generate new if there is none
        keystore = KeyStore()
        keystore.load_keys(self.device_name, uuid)

        # store backend public keys in keystore
        keystore.insert_verifying_key("demo", self.UUID_DEMO, self.PUB_DEMO)
        keystore.insert_verifying_key("prod", self.UUID_PROD, self.PUB_PROD)

        # after boot or restart try to register certificate
        cert = keystore.get_certificate(self.uuid)
        logger.debug("** key certificate : {}".format(json.dumps(cert)))

        # initialize ubirch protocol
        self.ubirch = ProtoImpl(keystore)

        key_registration = self.ubirch.message_signed(self.device_name, cert, UBIRCH_PROTOCOL_TYPE_REG)
        logger.debug("** key registration message [msgpack]: {}".format(binascii.hexlify(key_registration).decode()))

        # send key registration message to key service
        print("** registering identity at key service ...")
        r = self.api.register_identity(key_registration)
        if r.status_code == 200:
            r.close()
            print("** identity registered\n")
        else:
            logger.error(str(self.uuid) + ": ERROR: device identity not registered")
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.cfg.keyService, r.status_code,
                                                                         r.text))

    def send(self, data: dict):
        """
        Send data message to ubirch data service and certificate of the message to ubirch authentication service.
        Throws exception if sending message failed  or response from backend couldn't be verified.
        :param data: data map to to be sent
        """
        # pack data message containing measurements, device UUID and timestamp to ensure unique hash
        message, message_hash = pack_data_msgpack(self.uuid, data)
        logger.debug("** data message [msgpack]: {}".format(binascii.hexlify(message).decode()))
        logger.debug("** message hash [base64] : {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))

        # send message to data service
        print("** sending measurements ...")
        r = self.api.send_data(self.uuid, message)
        if r.status_code == 200:
            print("** measurements successfully sent\n")
            r.close()
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.cfg.data, r.status_code, r.text))

        # create UPP with the data message hash
        upp = self.ubirch.message_chained(self.device_name, message_hash)
        logger.debug("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        # send UPP to authentication service
        print("** sending measurement certificate ...")
        r = self.api.send_upp(self.uuid, upp)
        if r.status_code == 200:
            print("hash: {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))
            print("** measurement certificate successfully sent\n")

            # verify response from server
            response_content = r.content
            logger.debug(
                "** verifying response from {}: {}".format(self.api.cfg.niomon, binascii.hexlify(response_content)))
            verified = self.ubirch.message_verify(self.device_name, response_content)
            if not verified:
                raise Exception(
                    "!! signature verification failed: {} ".format(binascii.hexlify(response_content).decode()))
            logger.debug("** response verified\n")
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.cfg.niomon, r.status_code, r.text))

        if not self.verify_hash_in_backend(message_hash):
            raise Exception("!! backend verification of hash {} failed.".format(message_hash))

    def verify_hash_in_backend(self, message_hash) -> bool:
        """verify that hash has been stored and chained in backend"""
        print("** verifying hash in backend ...")
        retries = 4
        while retries > 0:
            time.sleep(0.5)
            r = self.api.verify(message_hash)
            if r.status_code == 200:
                print("** backend verification successful: {}".format(r.text))
                return True
            else:
                r.close()
                print("Hash could not be verified yet. Retry... ({} attempt(s) left)".format(retries))
                retries -= 1
        return False
