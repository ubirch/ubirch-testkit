import binascii
import json
import logging
import asn1
import machine
import os
import time
from network import LTE
from uuid import UUID
from config import Config
from .ubirch_data_packer import pack_data_msgpack
from .ubirch_sim import SimProtocol
from .ubirch_api import API

logger = logging.getLogger(__name__)


def asn1tosig(data: bytes):
    s1 = asn1.asn1_node_root(data)
    a1 = asn1.asn1_node_first_child(data, s1)
    part1 = asn1.asn1_get_value(data, a1)
    a2 = asn1.asn1_node_next(data, a1)
    part2 = asn1.asn1_get_value(data, a2)
    if len(part1) > 32: part1 = part1[1:]
    if len(part2) > 32: part2 = part2[1:]
    return part1 + part2


def get_certificate(key_entry_id: str, proto: SimProtocol) -> str:
    """
    Get a signed json with the key registration request until CSR handling is in place.
    """
    # TODO fix handling of key validity (will be fixed by handling CSR generation through SIM card)
    device_uuid = proto.get_uuid(key_entry_id)
    TIME_FMT = '{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.000Z'
    now = machine.RTC().now()
    created = not_before = TIME_FMT.format(now[0], now[1], now[2], now[3], now[4], now[5])
    later = time.localtime(time.mktime(now) + 30758400)
    not_after = TIME_FMT.format(later[0], later[1], later[2], later[3], later[4], later[5])
    pub_base64 = binascii.b2a_base64(proto.get_key(key_entry_id)).decode()[:-1]
    # json must be compact and keys must be sorted alphabetically
    REG_TMPL = '{{"algorithm":"ecdsa-p256v1","created":"{}","hwDeviceId":"{}","pubKey":"{}","pubKeyId":"{}","validNotAfter":"{}","validNotBefore":"{}"}}'
    REG = REG_TMPL.format(created, str(device_uuid), pub_base64, pub_base64, not_after, not_before).encode()
    # get the ASN.1 encoded signature and extract the signature bytes from it
    signature = asn1tosig(proto.sign(key_entry_id, REG, 0x00))
    return '{{"pubKeyInfo":{},"signature":"{}"}}'.format(REG.decode(), binascii.b2a_base64(signature).decode()[:-1])


class UbirchSimClient:

    def __init__(self, lte: LTE, cfg: Config):

        # initialize the ubirch protocol interface and backend API
        self.device_name = "ukey"
        self.api = API(cfg)
        self.ubirch = SimProtocol(lte=lte, at_debug=cfg.debug)

        # get IMSI from SIM
        imsi = self.ubirch.get_imsi()
        print("IMSI: " + imsi)

        # load PIN or bootstrap if PIN unknown
        pin_file = imsi + ".bin"
        pin = ""
        if pin_file in os.listdir('.'):
            print("loading PIN for " + imsi)
            with open(pin_file, "rb") as f:
                pin = f.readline().decode()
        else:
            print("bootstrapping SIM identity " + imsi)
            r = self.api.bootstrap_sim_identity(imsi)
            if r.status_code == 200:
                info = json.loads(r.content)
                print("bootstrapping successful: " + info)
                pin = info['pin']
                with open(pin_file, "wb") as f:
                    f.write(pin.encode())
            else:
                raise Exception("bootstrapping failed with status code {}: {}".format(r.status_code, r.text))

        # use PIN to authenticate against the SIM application
        if not self.ubirch.sim_auth(pin):
            raise Exception("PIN not accepted")

        self.uuid = self.ubirch.get_uuid(self.key_name)

        # after boot or restart try to register certificate
        # create a certificate for the device and register public key at ubirch key service
        # todo this will be replaced by the X.509 certificate from the SIM card
        key_registration = get_certificate(self.key_name, self.ubirch).encode()

        ##################################################################################
        # send key registration message to key service
        print("** registering identity at key service ...")
        r = self.api.register_identity(key_registration)
        if r.status_code == 200:
            r.close()
            print("** identity registered\n")
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.cfg.keyService, r.status_code,
                                                                         r.text))

    def send(self, data: dict):
        """
        Send data message to ubirch data service and certificate of the message to ubirch authentication service.
        Throws exception if sending message failed  or response from backend couldn't be verified.
        :param data: data map to to be sent
        """
        # pack data message containing measurements, device UUID and timestamp to ensure unique hash
        message, message_hash = pack_data_msgpack(self.uuid, data)
        logger.debug("** data message [msgpack]: {}".format(binascii.hexlify(message).decode()))
        logger.debug("** message hash [base64] : {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))

        # send message to data service
        print("** sending measurements ...")
        r = self.api.send_data(self.uuid, message)
        if r.status_code == 200:
            print("** measurements successfully sent\n")
            r.close()
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.cfg.data, r.status_code, r.text))

        # create UPP with the data message hash
        upp = self.ubirch.message_chained(self.device_name, message_hash)
        logger.debug("** UPP [msgpack]: {}".format(binascii.hexlify(upp).decode()))

        # send UPP to authentication service
        print("** sending measurement certificate ...")
        r = self.api.send_upp(self.uuid, upp)
        if r.status_code == 200:
            print("hash: {}".format(binascii.b2a_base64(message_hash).decode().rstrip('\n')))
            print("** measurement certificate successfully sent\n")

            # verify response from server
            response_content = r.content
            try:
                logger.debug(
                    "** verifying response from {}: {}".format(self.api.cfg.niomon, binascii.hexlify(response_content)))
                self.ubirch.message_verify(self.key_name, response_content)
                logger.debug("** response verified\n")
            except Exception as e:
                raise Exception(
                    "!! response verification failed: {}. {} ".format(e, binascii.hexlify(response_content)))
        else:
            raise Exception(
                "!! request to {} failed with status code {}: {}".format(self.api.cfg.niomon, r.status_code, r.text))

        if not self.verify_hash_in_backend(message_hash):
            raise Exception("!! backend verification of hash {} failed.".format(message_hash))

    def verify_hash_in_backend(self, message_hash) -> bool:
        """verify that hash has been stored and chained in backend"""
        print("** verifying hash in backend ...")
        retries = 4
        while retries > 0:
            time.sleep(0.5)
            r = self.api.verify(message_hash)
            if r.status_code == 200:
                print("** backend verification successful: {}".format(r.text))
                return True
            else:
                r.close()
                print("Hash could not be verified yet. Retry... ({} attempt(s) left)".format(retries))
                retries -= 1
        return False
