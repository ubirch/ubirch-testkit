import binascii
import time
from .ubirch_api import API
import umsgpack as msgpack
from uuid import UUID
from hashlib import sha512


class UbirchClient:

    def __init__(self, cfg: dict, lte=None, uuid=None):
        self.debug = cfg['debug']
        self.api = API(cfg)

        if cfg['sim']:
            from .ubirch_sim_client import UbirchSimClient
            self.driver = UbirchSimClient(cfg, lte)
        else:
            from .ubirch_protocol_client import UbirchProtocolClient
            self.driver = UbirchProtocolClient(uuid)

        # after boot or restart try to register public key at ubirch key service
        key_registration = self.driver.get_certificate()
        if self.debug: print(key_registration.decode())

        # send key registration message to key service
        print("** registering identity at key service ...")
        r = self.api.register_identity(key_registration)
        if r.status_code == 200:
            r.close()
            print("** identity registered\n")
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.key_service_url, r.status_code,
                                                                         r.text))

    def seal_and_send(self, data: dict):
        """
        Send data message to ubirch data service and certificate of the message to ubirch authentication service.
        Throws exception if operation failed.
        :param data: data map to be sealed and sent
        """
        # pack data message containing measurements, device UUID and timestamp to ensure unique hash
        message, message_hash = self.pack_data_msgpack(self.driver.uuid, data)  # todo change to json

        # send data message to data service
        self.send_data(message)

        # seal the data message hash
        print("** sealing hash: {}".format(binascii.b2a_base64(message_hash).decode()))
        upp = self.driver.message_chained(self.driver.key_name, message_hash)
        if self.debug:
            print("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        # send the sealed hash to the ubirch backend to be anchored to the blockchain
        self.send_to_blockchain(upp)

        # verify with the ubirch backend that the hash has been received, verified and chained
        self.verify_hash_in_backend(message_hash)

    def pack_data_msgpack(self, uuid: UUID, data: dict) -> (bytes, bytes):
        """
        Generate a msgpack formatted message for the ubirch data service.
        The message contains the device UUID, timestamp and data to ensure unique hash.
        The sha512 hash of the message will be appended to the message.
        :param uuid: the device UUID
        :param data: the mapped data to be sent to the ubirch data service
        :return: the msgpack formatted message, the hash of the data message
        """
        # hint for the message format (version)
        MSG_TYPE = 1

        msg = [
            uuid.bytes,
            MSG_TYPE,
            int(time.time()),
            data,
            0
        ]

        # calculate hash of message (without last array element)
        serialized = msgpack.packb(msg)[0:-1]
        message_hash = sha512(serialized).digest()

        # replace last element in array with the hash
        msg[-1] = message_hash
        serialized = msgpack.packb(msg)

        if self.debug:
            print("** data message [msgpack]: {}".format(binascii.hexlify(serialized).decode()))
            print("** message hash [base64] : {}".format(binascii.b2a_base64(message_hash).decode()))

        return serialized, message_hash

    # todo def pack_data_json(uuid: UUID, data: dict) -> (bytes, bytes):

    def send_data(self, message):
        """
        Send a ubirch data message to the data service.
        Throws exception if sending failed.
        :param message: the ubirch data message todo msgpack OR json
        """
        print("** sending measurements ...")
        r = self.api.send_data(self.driver.uuid, message)
        if r.status_code == 200:
            print("** measurements successfully sent\n")
            r.close()
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.data_service_url, r.status_code,
                                                                         r.text))

    def send_to_blockchain(self, upp):
        """
        Send a UPP (ubirch protocol package) to the ubirch authentication service.
        Throws exception if sending or server response verification failed.
        :param upp: the UPP to be anchored to the blockchain
        """
        print("** sending measurement certificate ...")
        r = self.api.send_upp(self.driver.uuid, upp)
        if r.status_code == 200:
            print("** measurement certificate successfully sent\n")
            # verify response from server
            #  todo not implemented for SIM yet (missing server public keys)
            # self.verify_server_response(r.content)
            r.close()
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.verification_service_url,
                                                                         r.status_code, r.text))

    def verify_server_response(self, server_response):
        """
        Verify a response with the corresponding public key for the UUID in the UPP envelope.
        Throws exception if server response couldn't be verified with known key or if key for UUID unknown.
        :param server_response: the response from the ubirch backend
        """
        print("** verifying server response: {}".format(binascii.hexlify(server_response).decode()))
        if self.driver.message_verify(self.driver.key_name, server_response):
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
        raise Exception("!! backend verification of hash {} failed.".format(binascii.b2a_base64(message_hash).decode()))
