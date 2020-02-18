import os

import ed25519

from uuid import UUID


class KeyStore:
    """
    The ubirch key store handles the keys relevant for the ubirch protocol.
    """

    def __init__(self, uuid: UUID, cfg_root: str = "") -> None:
        self.uuid = uuid
        self._ks_file = str(uuid) + ".bin"
        self._cfg_root = cfg_root
        self._vks = {}
        self._load_keys()

    def _load_keys(self) -> None:
        """Load or create new crypto-keys. The keys are stored in a local key store."""
        if self._ks_file in os.listdir(self._cfg_root):
            print("** loading existing key pair for " + str(self.uuid))
            with open(self._cfg_root + self._ks_file, "rb") as kf:
                self._sk = ed25519.SigningKey(kf.read())
                self._vk = self._sk.get_verifying_key()
        else:
            print("** generating new key pair for " + str(self.uuid))
            (self._vk, self._sk) = ed25519.create_keypair()
            with open(self._cfg_root + self._ks_file, "wb") as kf:
                kf.write(self._sk.to_bytes())
        self.insert_verifying_key(self.uuid, self._vk)

    def insert_verifying_key(self, uuid: UUID, verifying_key: ed25519.VerifyingKey):
        self._vks[uuid.hex] = verifying_key

    def get_verifying_key(self, uuid: UUID) -> ed25519.VerifyingKey:
        try:
            return self._vks[uuid.hex]
        except KeyError:
            raise Exception("No known verifying key for UUID {}".format(uuid))

    def get_signing_key(self) -> ed25519.SigningKey:
        return self._sk

    def get_certificate(self) -> dict:
        """Get a self signed certificate for the public key"""

        pubkey = self._vk.to_bytes()
        created = os.stat(self._cfg_root + self._ks_file)[7]
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
