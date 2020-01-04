import binascii
import json
import os

import ed25519

import logging
import urequests as requests
from uuid import UUID
from .ubirch_protocol import Protocol, UBIRCH_PROTOCOL_TYPE_REG

logger = logging.getLogger(__name__)


class UbirchClient(Protocol):
    PUB_DEV = ed25519.VerifyingKey(
        b'\xa2\x40\x3b\x92\xbc\x9a\xdd\x36\x5b\x3c\xd1\x2f\xf1\x20\xd0\x20\x64\x7f\x84\xea\x69\x83\xf9\x8b\xc4\xc8\x7e\x0f\x4b\xe8\xcd\x66')  # public key for dev/demo
    PUB_PROD = ed25519.VerifyingKey(
        b'\xef\x80\x48\xad\x06\xc0\x28\x5a\xf0\x17\x70\x09\x38\x18\x30\xc4\x6c\xec\x02\x5d\x01\xd8\x60\x85\xe7\x5a\x4f\x00\x41\xc2\xe6\x90')  # public key for prod

    def __init__(self, uuid: UUID, headers: dict, register_url: str, update_url: str, cfg_root: str = ""):
        """
        Initialize the ubirch-protocol implementation and read existing
        key or generate a new key pair. Generating a new key pair requires
        the system time to be set or the certificate may be unusable.
        """
        super().__init__()

        self._uuid = uuid
        self._headers = headers
        self._register_url = register_url
        self._update_url = update_url
        self._env = update_url.split(".")[1]
        self._cfg_root = cfg_root
        self._key_file = str(uuid) + ".bin"
        if self._key_file in os.listdir(self._cfg_root):
            print("loading key pair for " + str(self._uuid))
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
        print("** key certificate : {}".format(json.dumps(cert)))
        upp = self.message_signed(self._uuid, UBIRCH_PROTOCOL_TYPE_REG, cert)
        print("** key registration message: {}".format(binascii.hexlify(upp).decode()))
        print("** sending key registration message to {}".format(self._register_url))
        r = requests.post(self._register_url,
                          headers={'Content-Type': 'application/octet-stream'},
                          data=upp)
        if r.status_code == 200:
            r.close()
            print(str(self._uuid) + ": identity registered\n")
        else:
            logger.error(str(self._uuid) + ": ERROR: device identity not registered")
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self._register_url, r.status_code, r.text))

    def _sign(self, uuid: str, message: bytes) -> bytes:
        return self._sk.sign(message)

    def _verify(self, uuid: UUID, message: bytes, signature: bytes) -> bytes:
        if str(uuid) == str(self._uuid):
            return self._vk.verify(signature, message)
        else:
            if self._env == "prod":
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
            "hwDeviceId": self._uuid.bytes,
            "pubKey": pubkey,
            "pubKeyId": pubkey,
            "validNotAfter": not_after,
            "validNotBefore": not_before
        }

    def send(self, payload: bytes):
        """
        Seal the data and send to backend. This includes creating a SHA512 hash of the data
        and sending it to the ubirch backend. Throws exception if message couldn't be sent
        or response couldn't be verified.
        :param payload: the UPP payload
        """
        print("\n** sending measurement certificate to {} ...".format(self._update_url))
        upp = self.message_chained(self._uuid, 0x00, payload)
        print(binascii.hexlify(upp).decode())

        r = requests.post(self._update_url, headers=self._headers, data=upp)
        if r.status_code == 200:
            print("hash: {}".format(binascii.b2a_base64(payload).decode('utf-8').rstrip('\n')))
            print("** UPP sent")
            try:
                self.message_verify(r.content)
            except Exception as e:
                raise Exception("!! response verification failed: {}. {}".format(e, binascii.hexlify(r.content)))
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self._update_url, r.status_code, r.text))
