import time

import ubinascii as binascii
from network import LTE

from .ubirch_api import API
from .ubirch_helpers import get_certificate, get_pin, pack_data_msgpack, hash
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
        message_hash = hash(message)  # todo create chained message with automatic hashing and retrieve hash from UPP
        if self.debug:
            print("** data message [msgpack]: {}".format(binascii.hexlify(message).decode()))
            print("** message hash [base64] : {}".format(binascii.b2a_base64(message_hash).decode()))

        # send data message to data service
        print("** sending measurements ...")
        self.api.send_data(self.uuid, message)

        # seal the data message hash
        print("** sealing hash: {}".format(binascii.b2a_base64(message_hash).decode()))
        upp = self.sim.message_chained(self.key_name, message_hash)
        if self.debug:
            print("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        # send the sealed hash to the ubirch backend to be anchored to the blockchain
        print("** sending measurement certificate ...")
        response = self.api.send_upp(self.uuid, upp)

        # verify response from server
        #  todo not implemented for SIM yet (missing server public keys)
        # self.verify_server_response(response)

        # verify that the hash was received and verifiable by the backend
        print("** verifying hash in backend ...")
        time.sleep(0.3)  # wait for the backend to be ready
        response = self.api.verify(message_hash, quick=True)
        if self.debug:
            print("** response: " + response.decode())

    def verify_server_response(self, server_response):
        """
        Verify a response from the ubirch backend.
        The verifying key must be stored in the SIM secure storage with the backend uuid as entry ID.
        Throws exception if server response couldn't be verified with known key or if key for UUID unknown.
        :param server_response: the response from the ubirch backend
        """
        print("** verifying server response: {}".format(binascii.hexlify(server_response).decode()))
        if self.sim.message_verify(self.key_name, server_response):
            print("** response verified\n")
        else:
            raise Exception("!! response verification failed: {} ".format(binascii.hexlify(server_response).decode()))

