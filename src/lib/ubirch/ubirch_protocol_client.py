import binascii
import ed25519
from uuid import UUID
from .ubirch_ks import KeyStore
from .ubirch_protocol import Protocol, UBIRCH_PROTOCOL_TYPE_REG


class UbirchProtocolClient(Protocol):
    UUID_DEMO = UUID(binascii.unhexlify("9d3c78ff22f34441a5d185c636d486ff"))  # UUID of dev/demo stage
    UUID_PROD = UUID(binascii.unhexlify("10b2e1a456b34fff9adacc8c20f93016"))  # UUID of prod stage
    PUB_DEMO = ed25519.VerifyingKey(binascii.unhexlify(
        "a2403b92bc9add365b3cd12ff120d020647f84ea6983f98bc4c87e0f4be8cd66"))  # public key for dev/demo stage
    PUB_PROD = ed25519.VerifyingKey(binascii.unhexlify(
        "ef8048ad06c0285af0177009381830c46cec025d01d86085e75a4f0041c2e690"))  # public key for prod stage

    def __init__(self, uuid: UUID, signatures: dict = None):
        self.key_name = "A"
        self.uuid = uuid
        self._keystore = KeyStore()

        # load existing key pair or generate new if there is none
        self._keystore.load_keys(self.key_name, uuid)

        # store backend public keys in keystore
        self._keystore.insert_verifying_key("demo", self.UUID_DEMO, self.PUB_DEMO)
        self._keystore.insert_verifying_key("prod", self.UUID_PROD, self.PUB_PROD)

        # initialize ubirch protocol
        super().__init__(self._keystore.names, signatures)

    def get_certificate(self) -> bytes:
        cert = self._keystore.get_certificate(self.key_name)
        return self.message_signed(self.key_name, cert, UBIRCH_PROTOCOL_TYPE_REG)

    def _sign(self, uuid: UUID, message: bytes) -> bytes:
        return self._keystore.get_signing_key(uuid).sign(message)

    def _verify(self, uuid: UUID, message: bytes, signature: bytes) -> bytes:
        return self._keystore.get_verifying_key(uuid).verify(signature, message)
