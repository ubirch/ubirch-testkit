import machine
import sys
import time


class Connection:

    def set_time(self, ntp: str) -> bool:
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

    def connect(self) -> bool:
        raise NotImplementedError

    def is_connected(self) -> bool:
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError


class NB_IoT(Connection):

    def __init__(self, lte: LTE, apn: str, band: int or None):
        self.lte = lte

        if not self.attach(apn, band):
            raise OSError("!! unable to attach to NB-IoT network.")
        if not self.connect():
            raise OSError("!! unable to connect to NB-IoT network.")
        if not self.set_time('185.15.72.251'):
            raise OSError("!! unable to set time.")

    def attach(self, apn: str, band: int or None) -> bool:
        sys.stdout.write("++ attaching to the NB-IoT network")
        self.lte.attach(band=band, apn=apn)
        i = 0
        while not self.lte.isattached() and i < 60:
            i += 1
            machine.idle()
            time.sleep(1.0)
            sys.stdout.write(".")
        print("")
        if self.lte.isattached():
            print("-- attached: {} s".format(i))
            return True
        return False

    def connect(self) -> bool:
        sys.stdout.write("++ connecting to the NB-IoT network")
        self.lte.connect()  # start a data session and obtain an IP address
        i = 0
        while not self.lte.isconnected() and i < 60:
            i += 1
            machine.idle()
            time.sleep(1.0)
            sys.stdout.write(".")
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


class WIFI(Connection):

    def __init__(self, networks: dict):
        from network import WLAN
        self.wlan = WLAN(mode=WLAN.STA)
        self.networks = networks
        if not self.connect():
            raise OSError("!! unable to connect to WIFI network.")
        if not self.set_time('pool.ntp.org'):
            raise OSError("!! unable to set time.")

    def connect(self) -> bool:
        for _ in range(4):
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
            print("!! no usable networks found, trying again in 30s")
            print("!! available networks:")
            print("!! " + repr([net.ssid for net in nets]))
            machine.idle()
            time.sleep(30)
        return False

    def is_connected(self) -> bool:
        return self.wlan.isconnected()

    def disconnect(self):
        self.wlan.disconnect()


def init_connection(lte: LTE, cfg: dict) -> Connection:
    if cfg['connection'] == "wifi":
        return WIFI(cfg['networks'])
    elif cfg['connection'] == "nbiot":
        return NB_IoT(lte, cfg['apn'], cfg['band'])
    else:
        raise Exception(
            "Connection type {} not supported. Supported types: 'wifi' and 'nbiot'".format(cfg['connection']))
