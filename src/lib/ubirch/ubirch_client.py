import binascii
import json
import os

import ed25519

import logging
from uuid import UUID
from .ubirch_api import API
from .ubirch_protocol import Protocol, UBIRCH_PROTOCOL_TYPE_REG

logger = logging.getLogger(__name__)


def get_env(cfg: dict):
    if 'env' in cfg.keys():
        return cfg['env']
    else:
        return cfg['niomon'].split(".")[1]


class UbirchClient(Protocol):
    PUB_DEV = ed25519.VerifyingKey(
        b'\xa2\x40\x3b\x92\xbc\x9a\xdd\x36\x5b\x3c\xd1\x2f\xf1\x20\xd0\x20\x64\x7f\x84\xea\x69\x83\xf9\x8b\xc4\xc8\x7e\x0f\x4b\xe8\xcd\x66')  # public key for dev/demo stage
    PUB_PROD = ed25519.VerifyingKey(
        b'\xef\x80\x48\xad\x06\xc0\x28\x5a\xf0\x17\x70\x09\x38\x18\x30\xc4\x6c\xec\x02\x5d\x01\xd8\x60\x85\xe7\x5a\x4f\x00\x41\xc2\xe6\x90')  # public key for prod stage

    def __init__(self, uuid: UUID, cfg: dict, cfg_root: str = ""):
        """
        Initialize the ubirch-protocol implementation and read existing
        key or generate a new key pair. Generating a new key pair requires
        the system time to be set or the certificate may be unusable.
        """
        super().__init__()

        self.uuid = uuid
        self.env = get_env(cfg)
        self.auth = cfg['password']
        self.api = API(self.uuid, self.env, self.auth)

        # check for key pair and generate new if there is none
        self._cfg_root = cfg_root
        self._key_file = str(uuid) + ".bin"
        if self._key_file in os.listdir(self._cfg_root):
            print("loading key pair for " + str(self.uuid))
            with open(self._cfg_root + self._key_file, "rb") as kf:
                self._sk = ed25519.SigningKey(kf.read())
                self._vk = self._sk.get_verifying_key()
        else:
            print("generating new key pair for " + str(uuid))
            (self._vk, self._sk) = ed25519.create_keypair()
            with open(self._cfg_root + self._key_file, "wb") as kf:
                kf.write(self._sk.to_bytes())

        # after boot or restart try to register certificate
        cert = self.get_certificate()
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
                "!! request failed with status code {}: {}".format(r.status_code, r.text))

    def _sign(self, uuid: str, message: bytes) -> bytes:
        return self._sk.sign(message)

    def _verify(self, uuid: UUID, message: bytes, signature: bytes) -> bytes:
        if str(uuid) == str(self.uuid):
            return self._vk.verify(signature, message)
        else:
            if self.env == "prod":
                return self.PUB_PROD.verify(signature, message)
            else:
                return self.PUB_DEV.verify(signature, message)

    def get_certificate(self) -> dict or None:
        """Get a self signed certificate for the public key"""

        pubkey = self._vk.to_bytes()
        created = os.stat(self._cfg_root + self._key_file)[7]
        not_before = created
        # TODO fix handling of key validity
        not_after = created + 30758400
        return {
            "algorithm": 'ECC_ED25519',
            "created": created,
            "hwDeviceId": self.uuid.bytes,
            "pubKey": pubkey,
            "pubKeyId": pubkey,
            "validNotAfter": not_after,
            "validNotBefore": not_before
        }

    def send(self, data: dict):
        """
        Send data message to ubirch data service. On success, send certificate of the message
        to ubirch authentication service.
        Throws exception if message couldn't be sent or response couldn't be verified.
        :param data: a map containing the data to be sent
        """
        # pack data message with measurements, device UUID, timestamp and hash of the message
        message, message_hash = self.api.pack_data_message(data)
        logger.debug("** data message [msgpack]: {}".format(binascii.hexlify(message).decode()))
        logger.debug("** hash: {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))

        # send data message to data service
        print("** sending measurements ...")
        r = self.api.send_data(message)
        if r.status_code == 200:
            print("** measurements successfully sent\n")
            r.close()
        else:
            raise Exception(
                "!! request failed with status code {}: {}".format(r.status_code, r.text))

        # create UPP with the data message hash
        upp = self.message_chained(self.uuid, 0x00, message_hash)
        logger.debug("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        #  send UPP to niomon
        print("** sending measurement certificate ...")
        r = self.api.send_upp(upp)
        if r.status_code == 200:
            print("hash: {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))
            print("** measurement certificate successfully sent\n")
            try:
                self.message_verify(r.content)
            except Exception as e:
                raise Exception("!! response verification failed: {}. {}".format(e, binascii.hexlify(r.content)))
        else:
            raise Exception(
                "!! request failed with status code {}: {}".format(r.status_code, r.text))
