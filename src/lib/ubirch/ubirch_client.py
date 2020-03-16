import time
import ubinascii as binascii
from network import LTE
from .ubirch_api import API
from .ubirch_helpers import get_certificate, get_pin, pack_data_msgpack, get_payload
from .ubirch_sim import SimProtocol


class UbirchClient:

    def __init__(self, cfg: dict, lte: LTE):
        self.debug = cfg['debug']
        self.key_name = "A"  # fixme -> "ukey"
        self.api = API(cfg)
        self.bootstrap_service_url = cfg['bootstrap']
        self.auth = cfg['password']
        self.sim = SimProtocol(lte=lte)

        # get IMSI from SIM
        imsi = self.sim.get_imsi()
        print("** IMSI   : " + imsi)

        # unlock SIM
        pin = get_pin(imsi, self.api)
        if not self.sim.sim_auth(pin):
            raise Exception("PIN not accepted")

        # get UUID from SIM
        self.uuid = self.sim.get_uuid(self.key_name)
        print("** UUID   : " + str(self.uuid) + "\n")

        # after boot or restart try to register public key at ubirch key service
        print("** registering identity at key service ...")
        key_registration = get_certificate(self.uuid, self.sim, self.key_name)
        self.api.register_identity(key_registration)

    def send(self, data: dict):
        """
        Send data message to ubirch data service and certificate of the message to ubirch authentication service.
        Throws exception if operation failed.
        :param data: data map to be sealed and sent
        """
        # pack data message containing measurements, device UUID and timestamp to ensure unique hash
        message = pack_data_msgpack(self.uuid, data)
        if self.debug: print("** data message [msgpack]: {}".format(binascii.hexlify(message).decode()))

        # send data message to data service
        print("** sending measurements ...")
        self.api.send_data(self.uuid, message)

        # seal the data message (data message will be hashed and inserted into UPP as payload by SIM card)
        upp = self.sim.message_chained(self.key_name, message, hash_before_sign=True)
        if self.debug: print("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        # send UPP to the ubirch authentication service to be anchored to the blockchain
        print("** sending measurement certificate ...")
        self.api.send_upp(self.uuid, upp)

        # retrieve message hash from generated UPP for verification
        message_hash = get_payload(upp)
        print("** hash: {}".format(binascii.b2a_base64(message_hash).decode()))

        # verify that the hash was received and verifiable by the backend
        print("** verifying hash in backend ...")
        time.sleep(0.2)  # wait for the backend to be ready
        response = self.api.verify(message_hash, quick=True)
        if self.debug: print("** verification service response: " + response.decode())
