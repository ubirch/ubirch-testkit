from binascii import unhexlify, a2b_base64
from uuid import UUID

from ubirch import SimProtocol

server_identities = {
    "dev": {
        "UUID": "9d3c78ff22f34441a5d185c636d486ff",
        "pubKey": {
            "ECDSA": "LnU8BkvGcZQPy5gWVUL+PHA0DP9dU61H8DBO8hZvTyI7lXIlG1/oruVMT7gS2nlZDK9QG+ugkRt/zTrdLrAYDA=="
        }
    },
    "demo": {
        "UUID": "0710423518924020904200003c94b60b",
        "pubKey": {
            "ECDSA": "xm+iIomBRjR3QdvLJrGE1OBs3bAf8EI49FfgBriRk36n4RUYX+0smrYK8tZkl6Lhrt9lzjiUGrXGijRoVE+UjA=="
        }
    },
    "prod": {
        "UUID": "10b2e1a456b34fff9adacc8c20f93016",
        "pubKey": {
            "ECDSA": "pJdYoJN0N3QTFMBVjZVQie1hhgumQVTy2kX9I7kXjSyoIl40EOa9MX24SBAABBV7xV2IFi1KWMnC1aLOIvOQjQ=="
        }
    },
}


class UbirchClient:
    def __init__(self, sim: SimProtocol, env: str):
        self.sim = sim

        self._store_backend_public_keys(env=env)

    def _store_backend_public_keys(self, env: str):
        """
        Store the UBIRCH backend public key in the SIM cards secure storage
        Throws exception if operation fails.
        """
        if env not in server_identities.keys():
            raise Exception("invalid ubirch backend environment: {}".format(env))

        uuid = UUID(unhexlify(server_identities[env]["UUID"]))
        pkey = a2b_base64(server_identities[env]["pubKey"]["ECDSA"])

        # store public key of ubirch backend on the SIM card
        # TODO implement way to update verification key on SIM
        if not self.sim.entry_exists(env):
            self.sim.store_public_key(env, uuid, pkey)
