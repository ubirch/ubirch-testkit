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
        self.key_name = "ukey"
        self.api = API(cfg)
        self.sim = SimProtocol(lte=lte, at_debug=cfg['debug'])

        # unlock SIM
        pin = bootstrap(imsi, self.api)
        self.sim.sim_auth(pin)

        # get UUID from SIM
        self.uuid = self.sim.get_uuid(self.key_name)
        print("** UUID   : " + str(self.uuid) + "\n")

    def send(self, data: dict):
        """
        Send data message to ubirch data service and certificate of the message to ubirch authentication service.
        Throws exception if operation failed.
        :param data: data map to be sealed and sent
        """
        # pack data message containing measurements, device UUID and timestamp to ensure unique hash
        message = pack_data_json(self.uuid, data)
        print("** data message [json]: {}\n".format(message.decode()))

        # seal the data message (data message will be hashed and inserted into UPP as payload by SIM card)
        upp = self.sim.message_chained(self.key_name, message, hash_before_sign=True)
        print("** UPP [msgpack]: {} (base64: {})\n".format(hexlify(upp).decode(),
                                                           b2a_base64(upp).decode().rstrip('\n')))

        # send data message to data service
        print("** sending data message ...\n")
        self.api.send_data(self.uuid, message)

        # send UPP to the ubirch authentication service to be anchored to the blockchain
        print("** sending UPP ...\n")
        self.api.send_upp(self.uuid, upp)

        # retrieve data message hash from generated UPP for verification
        message_hash = get_upp_payload(upp)
        print("** data message hash: {}".format(b2a_base64(message_hash).decode()))
