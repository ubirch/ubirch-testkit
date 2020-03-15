import os
import time
from hashlib import sha512

import machine
import ubinascii as binascii
import ujson as json
from network import LTE

import asn1
import umsgpack as msgpack
from uuid import UUID
from .ubirch_api import API
from .ubirch_sim import SimProtocol


def asn1tosig(data: bytes):
    s1 = asn1.asn1_node_root(data)
    a1 = asn1.asn1_node_first_child(data, s1)
    part1 = asn1.asn1_get_value(data, a1)
    a2 = asn1.asn1_node_next(data, a1)
    part2 = asn1.asn1_get_value(data, a2)
    if len(part1) > 32: part1 = part1[1:]
    if len(part2) > 32: part2 = part2[1:]
    return part1 + part2


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
        pin = self._get_pin(imsi)
        if not self.sim.sim_auth(pin):
            raise Exception("PIN not accepted")

        # get UUID from SIM
        self.uuid = self.sim.get_uuid(self.key_name)
        print("** UUID   : " + str(self.uuid) + "\n")

        # after boot or restart try to register public key at ubirch key service
        print("** registering identity at key service ...")
        key_registration = self._get_certificate()
        r = self.api.register_identity(key_registration)
        if r.status_code == 200:
            r.close()
            print("** identity registered\n")
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.key_service_url, r.status_code,
                                                                         r.text))

    def _get_pin(self, imsi: str) -> str:
        # load PIN or bootstrap if PIN unknown
        pin_file = imsi + ".bin"
        pin = ""
        if pin_file in os.listdir('.'):
            print("loading PIN for " + imsi + "\n")
            with open(pin_file, "rb") as f:
                pin = f.readline().decode()
        else:
            print("bootstrapping SIM identity " + imsi)
            r = self.api.bootstrap_sim_identity(imsi)
            if r.status_code == 200:
                info = json.loads(r.content)
                print("bootstrapping successful: " + repr(info) + "\n")
                pin = info['pin']
                with open(pin_file, "wb") as f:
                    f.write(pin.encode())
            else:
                raise Exception("bootstrapping failed with status code {}: {}".format(r.status_code, r.text))
        return pin

    def _get_certificate(self) -> bytes:
        """
        Get a signed json with the key registration request until CSR handling is in place.
        TODO this will be replaced by the X.509 certificate from the SIM card
        """
        TIME_FMT = '{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.000Z'
        now = machine.RTC().now()
        created = not_before = TIME_FMT.format(now[0], now[1], now[2], now[3], now[4], now[5])
        later = time.localtime(time.mktime(now) + 30758400)
        not_after = TIME_FMT.format(later[0], later[1], later[2], later[3], later[4], later[5])
        pub_base64 = binascii.b2a_base64(self.sim.get_key(self.key_name)).decode()[:-1]
        # json must be compact and keys must be sorted alphabetically
        REG_TMPL = '{{"algorithm":"ecdsa-p256v1","created":"{}","hwDeviceId":"{}","pubKey":"{}","pubKeyId":"{}","validNotAfter":"{}","validNotBefore":"{}"}}'
        REG = REG_TMPL.format(created, str(self.uuid), pub_base64, pub_base64, not_after, not_before).encode()
        # get the ASN.1 encoded signature and extract the signature bytes from it
        signature = asn1tosig(self.sim.sign(self.key_name, REG, 0x00))
        return '{{"pubKeyInfo":{},"signature":"{}"}}'.format(REG.decode(),
                                                             binascii.b2a_base64(signature).decode()[:-1]).encode()

    def send(self, data: dict):
        """
        Send data message to ubirch data service and certificate of the message to ubirch authentication service.
        Throws exception if operation failed.
        :param data: data map to be sealed and sent
        """
        # pack data message containing measurements, device UUID and timestamp to ensure unique hash
        message, message_hash = self.pack_data_msgpack(self.uuid, data)  # todo change to json

        # send data message to data service
        self.send_data(message)

        # seal the data message hash
        print("** sealing hash: {}".format(binascii.b2a_base64(message_hash).decode()))
        upp = self.sim.message_chained(self.key_name, message_hash)
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
        r = self.api.send_data(self.uuid, message)
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
        r = self.api.send_upp(self.uuid, upp)
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
