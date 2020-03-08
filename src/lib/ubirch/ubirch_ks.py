import os
import ed25519
from uuid import UUID


class KeyStore:
    """
    The ubirch key store handles the keys relevant for the ubirch protocol.
    """

    def __init__(self, cfg_root: str = "") -> None:
        self._cfg_root = cfg_root
        self.names = {}
        self._sks = {}
        self._vks = {}

    def load_keys(self, name: str, uuid: UUID) -> None:
        """Load or create new crypto-keys. The keys are stored in a local key file."""
        ks_file = str(uuid) + ".bin"
        if ks_file in os.listdir(self._cfg_root):
            print("** loading existing key pair for " + str(uuid))
            with open(self._cfg_root + ks_file, "rb") as kf:
                sk = ed25519.SigningKey(kf.read())
                self.insert_keypair(name, uuid, sk)
        else:
            print("** generating new key pair for " + str(uuid))
            (vk, sk) = ed25519.create_keypair()
            self.insert_keypair(name, uuid, sk)
            with open(self._cfg_root + ks_file, "wb") as kf:
                kf.write(sk.to_bytes())

    def insert_verifying_key(self, name: str, uuid: UUID, verifying_key: ed25519.VerifyingKey):
        self._vks[uuid.hex] = verifying_key
        self.names[name] = uuid

    def insert_keypair(self, name: str, uuid: UUID, signing_key: ed25519.SigningKey):
        self._sks[uuid.hex] = signing_key
        self.insert_verifying_key(name, uuid, signing_key.get_verifying_key())

    def get_verifying_key(self, uuid: UUID) -> ed25519.VerifyingKey:
        try:
            return self._vks[uuid.hex]
        except KeyError:
            raise Exception("No known verifying key for UUID {}".format(uuid))

    def get_signing_key(self, uuid: UUID) -> ed25519.SigningKey:
        try:
            return self._sks[uuid.hex]
        except KeyError:
            raise Exception("No known signing key for UUID {}".format(uuid))

    def get_verifying_key_with_name(self, name: str) -> ed25519.VerifyingKey:
        try:
            return self.get_verifying_key(self.names[name].hex)
        except KeyError:
            raise Exception("No known verifying key for name {}".format(name))

    def get_signing_key_with_name(self, name: str) -> ed25519.SigningKey:
        try:
            return self.get_signing_key(self.names[name].hex)
        except KeyError:
            raise Exception("No known signing key for name {}".format(name))

    def get_certificate(self, uuid: UUID) -> dict:
        """Get a self signed certificate for the public key"""

        pubkey = self.get_verifying_key(uuid).to_bytes()
        created = os.stat(self._cfg_root + str(uuid) + ".bin")[7]
        not_before = created
        # TODO fix handling of key validity
        not_after = created + 30758400
        return {
            "algorithm": 'ECC_ED25519',
            "created": created,
            "hwDeviceId": uuid.bytes,
            "pubKey": pubkey,
            "pubKeyId": pubkey,
            "validNotAfter": not_after,
            "validNotBefore": not_before
        }
