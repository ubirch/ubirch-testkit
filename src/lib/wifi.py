import time

import machine
from network import WLAN
import sys


def connect(networks: dict, timeout: int = 10, retries: int = 5):
    """
    connect to wifi access point
    :param: networks: dict of "ssid": "password"
    :param: timeout: a timeout, how long to wait for association
    :return:
    """
    # try to join wifi at startup
    wlan = WLAN(mode=WLAN.STA)
    connected = False
    while not connected:
        nets = wlan.scan()
        print("-- searching for wifi networks...")
        for net in nets:
            if net.ssid in networks:
                ssid = net.ssid
                password = networks[ssid]
                print('-- wifi network ' + ssid + ' found, connecting ...')
                wlan.connect(ssid, auth=(net.sec, password), timeout=timeout * 1000)
                while not wlan.isconnected():
                    machine.idle()  # save power while waiting
                print('-- wifi network connected')
                print('-- IP address: ' + str(wlan.ifconfig()))
                rtc = machine.RTC()
                rtc.ntp_sync('pool.ntp.org', 3600)
                while not rtc.synced():
                    time.sleep(1)
                print('-- current time: ' + str(rtc.now()) + "\n")
                return
        if retries > 0:
            print("!! no usable networks found, trying again in 30s")
            print("!! available networks:")
            print("!! " + repr([net.ssid for net in nets]))
            retries -= 1
            time.sleep(30)
        else:
            raise Exception("network association failed with too many retries")

def set_time():
    rtc = machine.RTC()
    rtc.ntp_sync('131.188.3.221', 3600)
    while not rtc.synced():
        sys.stdout.write(".")
        time.sleep(1)
    print('-- current time: ' + str(rtc.now()) + "\n")
