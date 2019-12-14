import sys
import time

import machine
from network import WLAN


def connect(wlan: WLAN, networks: dict, retries: int = 5) -> bool:
    """
    connect to wifi access point
    :param: networks: dict of "ssid": "password"
    :return:
    """
    while True:
        nets = wlan.scan()
        print("-- searching for wifi networks...")
        for net in nets:
            if net.ssid in networks:
                ssid = net.ssid
                password = networks[ssid]
                print('-- wifi network ' + ssid + ' found, connecting ...')
                wlan.connect(ssid, auth=(net.sec, password), timeout=5000)
                while not wlan.isconnected():
                    machine.idle()  # save power while waiting
                print('-- wifi network connected')
                print('-- IP address: ' + str(wlan.ifconfig()))
                return True
        if retries > 0:
            print("!! no usable networks found, trying again in 30s")
            print("!! available networks:")
            print("!! " + repr([net.ssid for net in nets]))
            retries -= 1
            time.sleep(30)
        else:
            return False


def set_time() -> bool:
    rtc = machine.RTC()
    i = 0
    sys.stdout.write("-- setting time")
    rtc.ntp_sync('pool.ntp.org', 3600)
    while not rtc.synced() and i < 120:
        sys.stdout.write(".")
        time.sleep(1)
        i += 1
    print("\n-- current time: " + str(rtc.now()) + "\n")
    return rtc.synced()
