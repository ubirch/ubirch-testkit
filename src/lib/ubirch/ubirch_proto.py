import os
import ed25519
import ubinascii as binascii

from .ubirch import Protocol
from utime import time
from uuid import UUID

class UbirchProtocol(Protocol):
    PUB_DEV = ed25519.VerifyingKey(b"\xa2\x40\x3b\x92\xbc\x9a\xdd\x36\x5b\x3c\xd1\x2f\xf1\x20\xd0\x20\x64\x7f\x84\xea\x69\x83\xf9\x8b\xc4\xc8\x7e\x0f\x4b\xe8\xcd\x66")

    def __init__(self, uuid: UUID):
        """
        Initialize the ubirch-protocol implementation and read existing
        key or generate a new key pair. Generating a new key pair requires
        the system time to be set or the certificate may be unusable.
        """
        super().__init__()
        self.uuid = uuid
        self.key_file = str(uuid)+".bin"
        if self.key_file in os.listdir("/flash"):
            print("loading key pair for "+str(uuid))
            with open("/flash/"+self.key_file, "rb") as kf:
                self.sk = ed25519.SigningKey(kf.read())
                self.vk = self.sk.get_verifying_key()
        else:
            print("generating new key pair for "+str(uuid))
            (self.vk, self.sk) = ed25519.create_keypair()
            with open("/flash/"+self.key_file, "wb") as kf:
                kf.write(self.sk.to_bytes())

    def _sign(self, uuid: str, message: bytes) -> bytes:
        return self.sk.sign(message)

    def _verify(self, uuid: UUID, message: bytes, signature: bytes) -> bytes:
        if uuid == self.uuid:
            return self.vk.verify(signature, message)
        else:
            return self.PUB_DEV.verify(signature, message)

    def get_certificate(self) -> dict or None:
        pubkey = self.vk.to_bytes()
        created = os.stat("/flash/"+self.key_file)[7]
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
