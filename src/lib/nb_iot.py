import sys
import time

from network import LTE

import logging

logger = logging.getLogger(__name__)


def attach(lte: LTE, apn: str) -> bool:
    lte.attach(band=8, apn=apn)
    i = 0
    print("++ attaching to the NB IoT network")
    while not lte.isattached() and i < 20:
        time.sleep(1.0)
        sys.stdout.write(".")
        i = i + 1
    print("")
    if lte.isattached():
        print("attached: " + str(i) + "s")
        return True
    return False


def connect(lte: LTE) -> bool:
    lte.connect()  # start a data session and obtain an IP address
    i = 0
    print("++ connecting to the NB IoT network")
    while not lte.isconnected() and i < 20:
        time.sleep(0.5)
        sys.stdout.write(".")
        i = i + 1
    print("")
    if lte.isconnected():
        print("connected: " + str(i * 2) + "s")
        # print('-- IP address: ' + str(lte.ifconfig()))
        return True
    return False
