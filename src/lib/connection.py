import machine
import sys
import time


class Connection:

    def connect(self):
        raise NotImplementedError

    def is_connected(self) -> bool:
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError


class NB_IoT(Connection):

    def __init__(self, lte: LTE, apn: str, band: int or None):
        self.lte = lte
        self.apn = apn
        self.band = band

    def attach(self):
        if self.lte.isattached():
            return

        sys.stdout.write("\tattaching to the NB-IoT network")
        self.lte.attach(band=self.band, apn=self.apn)
        i = 0
        while not self.lte.isattached() and i < 60:
            i += 1
            time.sleep(1.0)
            sys.stdout.write(".")
        if not self.lte.isattached():
            raise OSError("!! unable to attach to NB-IoT network.")

        print("\n\t\tattached: {} s".format(i))

    def connect(self):
        if self.lte.isconnected():
            return

        if not self.lte.isattached() and not self.attach():
            raise OSError("!! unable to attach to NB-IoT network.")

        sys.stdout.write("\tconnecting to the NB-IoT network")
        self.lte.connect()  # start a data session and obtain an IP address
        i = 0
        while not self.lte.isconnected() and i < 60:
            i += 1
            time.sleep(1.0)
            sys.stdout.write(".")
        if not self.lte.isconnected():
            raise OSError("!! unable to connect to NB-IoT network.")

        print("\n\t\tconnected: {} s".format(i))
        # print('-- IP address: ' + str(lte.ifconfig()))

    def is_connected(self) -> bool:
        return self.lte.isconnected()

    def disconnect(self):
        self.lte.disconnect()


class WIFI(Connection):

    def __init__(self, networks: dict):
        from network import WLAN
        self.wlan = WLAN(mode=WLAN.STA)
        self.networks = networks

    def connect(self):
        if self.is_connected():
            return

        for _ in range(4):
            nets = self.wlan.scan()
            print("\tsearching for wifi networks...")
            for net in nets:
                if net.ssid in self.networks:
                    ssid = net.ssid
                    password = self.networks[ssid]
                    print('\twifi network ' + ssid + ' found, connecting ...')
                    self.wlan.connect(ssid, auth=(net.sec, password), timeout=5000)
                    while not self.wlan.isconnected():
                        machine.idle()  # save power while waiting
                    print('\twifi network connected')
                    print('\tIP address: {}\n'.format(self.wlan.ifconfig()))
                    return
            print("!! no usable networks found, trying again in 30s")
            print("!! available networks:")
            print("!! " + repr([net.ssid for net in nets]))
            machine.idle()
            time.sleep(30)

        raise OSError("!! unable to connect to WIFI network.")

    def is_connected(self) -> bool:
        return self.wlan.isconnected()

    def disconnect(self):
        self.wlan.disconnect()


connectionInstance = None


def init_connection(lte: LTE, cfg: dict) -> Connection:
    global connectionInstance
    if connectionInstance is not None:
        return connectionInstance
    if cfg['connection'] == "wifi":
        connectionInstance = WIFI(cfg['networks'])
        return connectionInstance
    elif cfg['connection'] == "nbiot":
        connectionInstance = NB_IoT(lte, cfg['apn'], cfg['band'])
        return connectionInstance
    else:
        raise Exception(
            "Connection type {} not supported. Supported types: 'wifi' and 'nbiot'".format(cfg['connection']))
