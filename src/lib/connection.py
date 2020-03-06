import sys
import time
import machine
from config import Config


def set_time(ntp: str) -> bool:
    rtc = machine.RTC()
    i = 0
    sys.stdout.write("++ setting time")
    rtc.ntp_sync(ntp, 3600)
    while not rtc.synced() and i < 60:
        sys.stdout.write(".")
        time.sleep(1.0)
        i += 1
    print("\n-- current time: {}\n".format(rtc.now()))
    return rtc.synced()


class Connection:

    def __init__(self, cfg: Config):
        # LTE can only be instantiated once. Do it here if SIM is used so LTE instance can be used
        # for modem operations outside this class even if network connection is via WIFI.
        if cfg.sim:
            from network import LTE
            self.lte = LTE()

        if cfg.connection == "wifi":
            self.network = WIFI(cfg.networks)
        elif cfg.connection == "nbiot":
            self.network = NB_IoT(self.lte, cfg.apn)
        else:
            raise Exception(
                "Connection type {} not supported. Supported types: 'wifi' and 'nbiot'".format(cfg.connection))

    def connect(self) -> bool:
        return self.network.connect()

    def is_connected(self) -> bool:
        return self.network.is_connected()

    def disconnect(self):
        return self.network.disconnect()


class NB_IoT:

    def __init__(self, lte, apn: str):
        self.lte = lte
        if not self.attach(apn):
            raise OSError("!! unable to attach to NB-IoT network.")
        if not self.connect():
            raise OSError("!! unable to connect to NB-IoT network.")
        if not set_time('185.15.72.251'):
            raise OSError("!! unable to set time.")

    def attach(self, apn: str) -> bool:
        self.lte.attach(band=8, apn=apn)
        i = 0
        sys.stdout.write("++ attaching to the NB-IoT network")
        while not self.lte.isattached() and i < 60:
            time.sleep(1.0)
            sys.stdout.write(".")
            i += 1
        print("")
        if self.lte.isattached():
            print("-- attached: {} s".format(i))
            return True
        return False

    def connect(self) -> bool:
        self.lte.connect()  # start a data session and obtain an IP address
        i = 0
        sys.stdout.write("++ connecting to the NB-IoT network")
        while not self.lte.isconnected() and i < 60:
            time.sleep(1.0)
            sys.stdout.write(".")
            i += 1
        print("")
        if self.lte.isconnected():
            print("-- connected: {} s\n".format(i))
            # print('-- IP address: ' + str(lte.ifconfig()))
            return True
        return False

    def is_connected(self) -> bool:
        return self.lte.isconnected()

    def disconnect(self):
        self.lte.disconnect()


class WIFI:

    def __init__(self, networks: dict):
        from network import WLAN
        self.wlan = WLAN(mode=WLAN.STA)
        self.networks = networks
        if not self.connect():
            raise OSError("!! unable to connect to WIFI network.")
        if not set_time('pool.ntp.org'):
            raise OSError("!! unable to set time.")

    def connect(self) -> bool:
        retries = 5
        while True:
            nets = self.wlan.scan()
            print("++ searching for wifi networks...")
            for net in nets:
                if net.ssid in self.networks:
                    ssid = net.ssid
                    password = self.networks[ssid]
                    print('-- wifi network ' + ssid + ' found, connecting ...')
                    self.wlan.connect(ssid, auth=(net.sec, password), timeout=5000)
                    while not self.wlan.isconnected():
                        machine.idle()  # save power while waiting
                    print('-- wifi network connected')
                    print('-- IP address: {}\n'.format(self.wlan.ifconfig()))
                    return True
            if retries > 0:
                print("!! no usable networks found, trying again in 30s")
                print("!! available networks:")
                print("!! " + repr([net.ssid for net in nets]))
                retries -= 1
                time.sleep(30)
            else:
                return False

    def is_connected(self) -> bool:
        return self.wlan.isconnected()

    def disconnect(self):
        self.wlan.disconnect()
