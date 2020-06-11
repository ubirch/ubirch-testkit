import os
import time
from network import LTE
from ubinascii import b2a_base64, a2b_base64, hexlify, unhexlify
from uuid import UUID
from .ubirch_api import API
from .ubirch_helpers import *
from .ubirch_sim import SimProtocol


class UbirchClient:

    def __init__(self, cfg: dict, lte: LTE, imsi: str):
        vks = {
            "dev": a2b_base64(
                "LnU8BkvGcZQPy5gWVUL+PHA0DP9dU61H8DBO8hZvTyI7lXIlG1/oruVMT7gS2nlZDK9QG+ugkRt/zTrdLrAYDA=="),
            "demo": a2b_base64(
                "LnU8BkvGcZQPy5gWVUL+PHA0DP9dU61H8DBO8hZvTyI7lXIlG1/oruVMT7gS2nlZDK9QG+ugkRt/zTrdLrAYDA==")
        }
        uuids = {
            "dev": UUID(unhexlify("9d3c78ff22f34441a5d185c636d486ff")),
            "demo": UUID(unhexlify("9d3c78ff22f34441a5d185c636d486ff"))
        }

        self.key_name = "ukey"
        self.api = API(cfg)
        self.sim = SimProtocol(lte=lte, at_debug=cfg['debug'])

        # unlock SIM
        pin = bootstrap(imsi, self.api)
        if not self.sim.sim_auth(pin):
            raise Exception("PIN not accepted")

        # store public key of ubirch backend on the SIM card
        env = self.api.env
        if not self.sim.entry_exists(env):
            self.sim.store_public_key(env, uuids[env], vks[env])

        # get UUID from SIM
        self.uuid = self.sim.get_uuid(self.key_name)
        print("** UUID   : " + str(self.uuid) + "\n")

        # send a X.509 Certificate Signing Request for the public key to the ubirch identity service
        submit_csr(self.uuid, self.key_name, self.sim, self.api)

        # # register public key at ubirch key service todo will be replaced by X.509 cert
        # register_public_key(self.uuid, self.key_name, self.sim, self.api)

    def send(self, data: dict):
        """
        Send data message to ubirch data service and certificate of the message to ubirch authentication service.
        Throws exception if operation failed.
        :param data: data map to be sealed and sent
        """
        # pack data message containing measurements, device UUID and timestamp to ensure unique hash
        message = pack_data_json(self.uuid, data)
        print("** data message [json]: {}\n".format(message.decode()))

        # send data message to data service
        print("** sending data message ...\n")
        self.api.send_data(self.uuid, message)

        # seal the data message (data message will be hashed and inserted into UPP as payload by SIM card)
        upp = self.sim.message_chained(self.key_name, message, hash_before_sign=True)
        print("** UPP [msgpack]: {} (base64: {})\n".format(hexlify(upp).decode(),
                                                           b2a_base64(upp).decode().rstrip('\n')))

        # send UPP to the ubirch authentication service to be anchored to the blockchain
        print("** sending UPP ...\n")
        response = self.api.send_upp(self.uuid, upp)
        print("response: " + hexlify(response).decode())
        # verify the signature of the backend response with its public key
        try:
            fixed_upp = fix_upp_signature_format(response)
            print("fixed response: " + hexlify(fixed_upp).decode())
            if not self.sim.message_verify(self.api.env, fixed_upp):
                raise Exception("signature verification failed")
        except Exception as e:
            raise Exception("!! couldn't verify backend response: {} ({}) ".format(e, hexlify(response).decode()))

        # retrieve data message hash from generated UPP for verification
        message_hash = get_upp_payload(upp)
        print("** data message hash: {}".format(b2a_base64(message_hash).decode()))

        # # OPTIONAL # verify that the hash was received and verifiable by the backend
        # print("** verifying hash in backend (quick check) ...")
        # time.sleep(0.2)  # wait for the backend to be ready
        # response = self.api.verify(message_hash, quick=True)
        # print("** verification successful! response: " + response.decode())
