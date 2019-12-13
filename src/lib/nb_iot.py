import sys
import time

import machine
from network import LTE


def attach(lte: LTE, apn: str) -> bool:
    lte.attach(band=8, apn=apn)
    i = 0
    sys.stdout.write("++ attaching to the NB IoT network")
    while not lte.isattached() and i < 20:
        time.sleep(1.0)
        sys.stdout.write(".")
        i += 1
    print("")
    if lte.isattached():
        print("attached: " + str(i) + "s")
    return lte.isattached()


def connect(lte: LTE) -> bool:
    lte.connect()  # start a data session and obtain an IP address
    i = 0
    sys.stdout.write("++ connecting to the NB IoT network")
    while not lte.isconnected() and i < 20:
        time.sleep(0.5)
        sys.stdout.write(".")
        i += 1
    print("")
    if lte.isconnected():
        print("connected: " + str(i * 2) + "s")
        # print('-- IP address: ' + str(lte.ifconfig()))
    return lte.isconnected()


def set_time() -> bool:
    rtc = machine.RTC()
    i = 0
    sys.stdout.write("++ setting time")
    rtc.ntp_sync('185.15.72.251', 3600)
    while not rtc.synced() and i < 120:
        sys.stdout.write(".")
        time.sleep(1)
        i += 1
    print("\n-- current time: " + str(rtc.now()) + "\n")
    return rtc.synced()
