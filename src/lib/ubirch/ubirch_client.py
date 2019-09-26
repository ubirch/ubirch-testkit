import binascii
import os
import json
import ed25519
import urequests as requests
import umsgpack as msgpack

from .ubirch_protocol import *


class UbirchClient(Protocol):
    PUB_DEV = ed25519.VerifyingKey(b'\xa2\x40\x3b\x92\xbc\x9a\xdd\x36\x5b\x3c\xd1\x2f\xf1\x20\xd0\x20\x64\x7f\x84\xea\x69\x83\xf9\x8b\xc4\xc8\x7e\x0f\x4b\xe8\xcd\x66')

    def __init__(self, uuid: UUID, headers: dict, register_url: str, update_url: str, cfg_root: str = ""):
        """
        Initialize the ubirch-protocol implementation and read existing
        key or generate a new key pair. Generating a new key pair requires
        the system time to be set or the certificate may be unusable.
        """
        super().__init__()

        self._uuid = uuid
        self.__headers = headers
        self.__register_url = register_url
        self.__update_url = update_url
        self.__cfg_root = cfg_root
        self._key_file = str(uuid)+".bin"
        if self._key_file in os.listdir(self.__cfg_root):
            print("loading key pair for "+str(self._uuid))
            with open(self.__cfg_root+self._key_file, "rb") as kf:
                self.__sk = ed25519.SigningKey(kf.read())
                self._vk = self.__sk.get_verifying_key()
        else:
            print("generating new key pair for "+str(uuid))
            (self._vk, self.__sk) = ed25519.create_keypair()
            with open(self.__cfg_root+self._key_file, "wb") as kf:
                kf.write(self.__sk.to_bytes())

        # after boot or restart try to register certificate
        cert = self.get_certificate()
        upp = self.message_signed(self._uuid, UBIRCH_PROTOCOL_TYPE_REG, cert)
        r = requests.post(self.__register_url,
                          headers={'Content-Type': 'application/octet-stream'},
                          data=upp)
        if r.status_code == 200:
            print(str(self._uuid)+": identity registered")
        else:
            print(str(self._uuid)+": ERROR: device identity not registered")

    def _sign(self, uuid: str, message: bytes) -> bytes:
        return self.__sk.sign(message)

    def _verify(self, uuid: UUID, message: bytes, signature: bytes) -> bytes:
        if uuid == self._uuid:
            return self._vk.verify(signature, message)
        else:
            return self.PUB_DEV.verify(signature, message)

    def get_certificate(self) -> dict or None:
        """Get a self signed certificate for the public key"""

        pubkey = self._vk.to_bytes()
        created = os.stat(self.__cfg_root+self._key_file)[7]
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
        and sending it to the ubirch backend.
        :param payload: the original data (which will be hashed)
        :return: the parsed response and the REST response from the ubirch backend
        """
        upp = self.message_chained(self._uuid, 0x00, self._hash(payload))
        print(binascii.hexlify(upp))
        r = requests.post(self.__update_url, headers=self.__headers, data=upp)
        if r.status_code == 200:
            try:
                print("** verifying response from {}".format(self.__update_url))
                response = self.message_verify(r.content)
                print("** response verified: {}".format(response))
            except Exception as e:
                raise Exception("!! response verification failed: {}. {}".format(e, binascii.hexlify(r.content)))
        else:
            print(
                "!! request to {} failed with status code {}: {}".format(self.__update_url, r.status_code, r.text))

