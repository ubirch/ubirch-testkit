import time
import ubinascii as binascii
from network import LTE
from .ubirch_api import API
from .ubirch_helpers import get_certificate, get_pin, pack_data_json, get_upp_payload
from .ubirch_sim import SimProtocol


class UbirchClient:

    def __init__(self, cfg: dict, lte: LTE, imsi: str):
        self.key_name = "ukey"
        self.api = API(cfg)
        self.sim = SimProtocol(lte=lte, at_debug=cfg['debug'])

        # unlock SIM
        pin = get_pin(imsi, self.api)
        if not self.sim.sim_auth(pin):
            raise Exception("PIN not accepted")

        # get UUID from SIM
        self.uuid = self.sim.get_uuid(self.key_name)
        print("** UUID   : " + str(self.uuid) + "\n")

        # after boot or restart try to register public key at ubirch key service
        print("** registering public key at key service ...")
        key_registration = get_certificate(self.uuid, self.sim, self.key_name)
        self.api.register_identity(key_registration)

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
        print("** UPP [msgpack]: {} (base64: {})\n".format(binascii.hexlify(upp).decode(),
                                                           binascii.b2a_base64(upp).decode().rstrip('\n')))

        # send UPP to the ubirch authentication service to be anchored to the blockchain
        print("** sending UPP ...\n")
        self.api.send_upp(self.uuid, upp)

        # retrieve data message hash from generated UPP for verification
        message_hash = get_upp_payload(upp)
        print("** data message hash: {}".format(binascii.b2a_base64(message_hash).decode()))

        # # OPTIONAL # verify that the hash was received and verifiable by the backend
        # print("** verifying hash in backend (quick check) ...")
        # time.sleep(0.2)  # wait for the backend to be ready
        # response = self.api.verify(message_hash, quick=True)
        # print("** verification successful! response: " + response.decode())
