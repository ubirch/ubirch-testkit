import time

import ubinascii as binascii
from network import LTE

from urequests import Response
from .ubirch_api import API
from .ubirch_helpers import get_certificate, get_pin, pack_data_msgpack
from .ubirch_sim import SimProtocol


def _check_response(r: Response, url: str) -> bytes:
    if r.status_code == 200:
        print("** succeeded\n")
        response = r.content
        r.close()
        return response
    else:
        raise Exception(
            "!! request to {} failed with status code {}: {}".format(url, r.status_code, r.text))


class UbirchClient:

    def __init__(self, cfg: dict, lte: LTE):
        self.debug = cfg['debug']
        self.key_name = "A"
        self.api = API(cfg)
        self.bootstrap_service_url = cfg['bootstrap']
        self.auth = cfg['password']
        self.sim = SimProtocol(lte=lte, at_debug=self.debug)

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
        r = self.api.register_identity(key_registration)
        _check_response(r, self.api.key_service_url)

    def send(self, data: dict):
        """
        Send data message to ubirch data service and certificate of the message to ubirch authentication service.
        Throws exception if operation failed.
        :param data: data map to be sealed and sent
        """
        # pack data message containing measurements, device UUID and timestamp to ensure unique hash
        message, message_hash = pack_data_msgpack(self.uuid, data, self.debug)  # todo change to json

        # send data message to data service
        print("** sending measurements ...")
        r = self.api.send_data(self.uuid, message)
        _check_response(r, self.api.data_service_url)

        # seal the data message hash
        print("** sealing hash: {}".format(binascii.b2a_base64(message_hash).decode()))
        upp = self.sim.message_chained(self.key_name, message_hash)
        if self.debug:
            print("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        # send the sealed hash to the ubirch backend to be anchored to the blockchain
        print("** sending measurement certificate ...")
        r = self.api.send_upp(self.uuid, upp)
        _check_response(r, self.api.verification_service_url)

        # verify response from server
        #  todo not implemented for SIM yet (missing server public keys)
        # self.verify_server_response(response)

        # verify with the ubirch backend that the hash has been received, verified and chained
        self.verify_hash_in_backend(message_hash)

    def verify_server_response(self, server_response):
        """
        Verify a response with the corresponding public key for the UUID in the UPP envelope.
        Throws exception if server response couldn't be verified with known key or if key for UUID unknown.
        :param server_response: the response from the ubirch backend
        """
        print("** verifying server response: {}".format(binascii.hexlify(server_response).decode()))
        if self.sim.message_verify(self.key_name, server_response):
            print("** response verified\n")
        else:
            raise Exception("!! response verification failed: {} ".format(binascii.hexlify(server_response).decode()))

    def verify_hash_in_backend(self, message_hash):
        """
        Verify that a given hash has been stored and chained in the ubirch backend.
        Throws exception if backend verification failed.
        :param message_hash: the payload of the UPP to be verified in the backend
        """
        print("** verifying hash in backend ...")
        retries = 4
        while retries > 0:
            time.sleep(0.5)
            r = self.api.verify(message_hash)
            if r.status_code == 200:
                print("** backend verification successful: {}".format(r.text))
                return
            else:
                r.close()
                if self.debug:
                    print("Hash could not be verified yet. Retry... ({} attempt(s) left)".format(retries))
                retries -= 1
        raise Exception("!! backend verification of hash {} failed.".format(
            binascii.b2a_base64(message_hash).decode().rstrip('\n')))
