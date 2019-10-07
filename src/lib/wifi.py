import logging
import time

import machine
from network import WLAN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        logger.info("-- searching for wifi networks...")
        for net in nets:
            if net.ssid in networks:
                ssid = net.ssid
                password = networks[ssid]
                logger.info('-- wifi network ' + ssid + ' found, connecting ...')
                wlan.connect(ssid, auth=(net.sec, password), timeout=timeout * 1000)
                while not wlan.isconnected():
                    machine.idle()  # save power while waiting
                logger.info('-- wifi network connected')
                logger.info('-- IP address: ' + str(wlan.ifconfig()))
                rtc = machine.RTC()
                rtc.ntp_sync('pool.ntp.org', 3600)
                while not rtc.synced():
                    time.sleep(1)
                logger.info('-- current time: ' + str(rtc.now()) + "\n")
                return
        if retries > 0:
            logger.warning("!! no usable networks found, trying again in 30s")
            logger.info("!! available networks:")
            logger.info("!! " + repr([net.ssid for net in nets]))
            retries -= 1
            time.sleep(30)
        else:
            raise Exception("network association failed with too many retries")
