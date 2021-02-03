from binascii import unhexlify, a2b_base64
from uuid import UUID

from ubirch import SimProtocol


class UbirchClient:
    def __init__(self, sim: SimProtocol):
        self.sim = sim

        self.store_backend_public_keys()

    def store_backend_public_keys(self):
        """
        Store the UBIRCH backend public keys in the SIM cards secure storage
        Throws exception if operation fails.
        """
        backend_keys = {
            "dev": {
                "uuid": UUID(unhexlify("9d3c78ff22f34441a5d185c636d486ff")),
                "pubkey": a2b_base64(
                    "LnU8BkvGcZQPy5gWVUL+PHA0DP9dU61H8DBO8hZvTyI7lXIlG1/oruVMT7gS2nlZDK9QG+ugkRt/zTrdLrAYDA==")
            },
            "demo": {
                "uuid": UUID(unhexlify("0710423518924020904200003c94b60b")),
                "pubkey": a2b_base64(
                    "xm+iIomBRjR3QdvLJrGE1OBs3bAf8EI49FfgBriRk36n4RUYX+0smrYK8tZkl6Lhrt9lzjiUGrXGijRoVE+UjA==")
            },
            "prod": {
                "uuid": UUID(unhexlify("10b2e1a456b34fff9adacc8c20f93016")),
                "pubkey": a2b_base64(
                    "pJdYoJN0N3QTFMBVjZVQie1hhgumQVTy2kX9I7kXjSyoIl40EOa9MX24SBAABBV7xV2IFi1KWMnC1aLOIvOQjQ==")
            },
        }

        # store public keys of ubirch backend on the SIM card
        for name in ["dev", "demo", "prod"]:
            if not self.sim.entry_exists(name):
                self.sim.store_public_key(name, backend_keys.get(name).get("uuid"),
                                          backend_keys.get(name).get("pubkey"))
