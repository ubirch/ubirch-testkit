import sys
import time
import machine


class Connection():
    def connect(self) -> bool:
        raise NotImplementedError()

    def is_connected(self) -> bool:
        raise NotImplementedError()

    def disconnect(self):
        raise NotImplementedError()

    def set_time(self, ntp: str) -> bool:
        rtc = machine.RTC()
        i = 0
        sys.stdout.write("++ setting time")
        rtc.ntp_sync(ntp, 3600)
        while not rtc.synced() and i < 60:
            sys.stdout.write(".")
            time.sleep(1.0)
            i += 1
        print("\n-- current time: " + str(rtc.now()) + "\n")
        return rtc.synced()


class NB_IoT(Connection):
    from network import LTE

    def __init__(self, lte: LTE, apn: str):
        self.lte = lte
        if not self.attach(apn):
            raise ConnectionError("!! unable to attach to NB-IoT network.")
        if not self.connect():
            raise ConnectionError("!! unable to connect to NB-IoT network.")
        if not self.set_time('185.15.72.251'):
            raise ConnectionError("!! unable to set time.")

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
            print("-- attached: " + str(i) + "s")
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
            print("-- connected: " + str(i) + "s")
            # print('-- IP address: ' + str(lte.ifconfig()))
            return True
        return False

    def is_connected(self):
        return self.lte.isconnected()

    def disconnect(self):
        self.lte.disconnect()


class WIFI(Connection):
    from network import WLAN

    def __init__(self, wlan: WLAN, networks: dict):
        self.wlan = wlan
        self.networks = networks
        if not self.connect():
            raise ConnectionError("!! unable to connect to WIFI network.")
        if not self.set_time('pool.ntp.org'):
            raise ConnectionError("!! unable to set time.")

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
                    print('-- IP address: ' + str(self.wlan.ifconfig()))
                    return True
            if retries > 0:
                print("!! no usable networks found, trying again in 30s")
                print("!! available networks:")
                print("!! " + repr([net.ssid for net in nets]))
                retries -= 1
                time.sleep(30)
            else:
                return False

    def is_connected(self):
        return self.wlan.isconnected()

    def disconnect(self):
        """
        this is a dummy method!! It does not actually disconnect the WIFI connection!
        This method is only necessary, because LTE connections need to be dis- and re-connected regularly,
        but we don't want to actually disconnect WIFI
        """
        pass
