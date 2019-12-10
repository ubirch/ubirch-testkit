import json
import time

import machine
# Pycom specifics
import pycom

import logging
from pyboard import Pysense, Pytrack
# ubirch data client
from ubirch import UbirchDataClient
from uuid import UUID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rtc = machine.RTC()

setup_help_text = """
    * Copy the UUID and register your device at the Ubirch Web UI
    * Create a file \'config.json\' in the src directory of this project
        {
          "networks": {
            "<WIFI SSID>": "<WIFI PASSWORD>"
          },
          "type": "<TYPE: 'pysense' or 'pytrack'>",
          "password": "<password for ubirch auth and data service>",
          "keyService": "<URL of key registration service>",
          "niomon": "<URL of authentication service>",
          "data": "<URL of data service>"
        }
    * Upload the file to your device and run again.\n
    For more information, take a look at the README or STEPBYSTEP.md of this project.
"""


class Main:
    """
    |  UBIRCH example for pycom modules.
    |
    |  The devices creates a unique UUID and sends data to the ubirch data and auth services.
    |  At the initial start these steps are required:
    |
    |  - start the pycom module with this code
    |  - take note of the UUID printed on the serial console
    |  - register your device at the Ubirch Web UI
    |
    """

    def __init__(self) -> None:

        # generate UUID
        self.uuid = UUID(b'UBIR' + 2 * machine.unique_id())
        print("\n** UUID   : " + str(self.uuid) + "\n")

        # load configuration from config.json file
        # the config.json should be placed next to this file
        # {
        #    "connection": "<'wifi' or 'nbiot'>",
        #    "networks": {
        #      "<WIFI SSID>": "<WIFI PASSWORD>"
        #    },
        #    "apn": "<APN for NB IoT connection",
        #    "type": "<TYPE: 'pysense' or 'pytrack'>",
        #    "password": "<password for ubirch auth and data service>",
        #    "keyService": "<URL of key registration service>",
        #    "niomon": "<URL of authentication service>",
        #    "data": "<URL of data service>"
        # }
        try:
            with open('config.json', 'r') as c:
                self.cfg = json.load(c)
        except OSError:
            print(setup_help_text)
            while True:
                machine.idle()

        # create a text file for error logging
        with open('log.txt', 'a') as logfile:
            logfile.write("{} init\n".format(self.uuid))

        # connect device to network
        if self.cfg["connection"] == "wifi":
            import wifi
            from network import WLAN
            # try to connect via wifi, throws exception if no success
            self.wlan = WLAN(mode=WLAN.STA)
            wifi.connect(self.wlan, self.cfg['networks'])
            wifi.set_time()
        elif self.cfg["connection"] == "nbiot":
            import nb_iot
            from network import LTE
            self.lte = LTE()
            if not nb_iot.attach(self.lte, self.cfg["apn"]):
                self.log_and_print("ERROR: unable to attach to network. Resetting device...")
                time.sleep(5)
                machine.reset()
            if not nb_iot.connect(self.lte):
                self.log_and_print("ERROR: unable to connect to network. Resetting device...")
                time.sleep(5)
                machine.reset()

        # ubirch data client for setting up ubirch protocol, authentication and data service
        self.ubirch_data = UbirchDataClient(self.uuid, self.cfg)

        # initialize the sensor based on the type of the pycom add-on board
        if self.cfg["type"] == "pysense":
            self.sensor = Pysense()
        elif self.cfg["type"] == "pytrack":
            self.sensor = Pytrack()
        else:
            logger.error("Expansion board type not supported. This version supports types \"pysense\" and \"pytrack\"")

    def log_and_print(self, message: str):
        print(message)
        with open('log.txt', 'a') as logfile:
            logfile.write("{}: {}\n".format(str(rtc.now()), message))

    def prepare_data(self):
        """
        Prepare the data from the sensor module and return it in the format we need.
        :return: a dictionary (json) with the data
        """

        data = {
            "V": self.sensor.voltage()
        }

        if isinstance(self.sensor, Pysense) or isinstance(self.sensor, Pytrack):
            accel = self.sensor.accelerometer.acceleration()
            roll = self.sensor.accelerometer.roll()
            pitch = self.sensor.accelerometer.pitch()

            data.update({
                "AccX": accel[0],
                "AccY": accel[1],
                "AccZ": accel[2],
                "AccRoll": roll,
                "AccPitch": pitch
            })

        if isinstance(self.sensor, Pysense):
            data.update({
                "T": self.sensor.barometer.temperature(),
                "P": self.sensor.barometer.pressure(),
                # "Alt": self.sensor.altimeter.altitude(),
                "H": self.sensor.humidity.humidity(),
                "L_blue": self.sensor.light()[0],
                "L_red": self.sensor.light()[1]
            })

        if isinstance(self.sensor, Pytrack):
            data.update({
                "GPS_long": self.sensor.location.coordinates()[0],
                "GPS_lat": self.sensor.location.coordinates()[1]
            })

        return data

    def print_data(self, data: dict):
        print("{")
        for key in sorted(data):
            print("  \"{}\": {},".format(key, data[key]))
        print("}")

    def loop(self, interval: int = 60):
        # disable blue heartbeat blink
        pycom.heartbeat(False)
        while True:
            start_time = time.time()
            pycom.rgbled(0x002200)

            # get data
            print("** getting measurements:")
            data = self.prepare_data()
            self.print_data(data)

            # make sure device is still connected
            if self.cfg["connection"] == "wifi" and not self.wlan.isconnected():
                import wifi
                pycom.rgbled(0x440044)
                self.log_and_print("!! lost wifi connection, trying to reconnect ...")
                wifi.connect(self.wlan, self.cfg['networks'])
                pycom.rgbled(0x002200)
            elif self.cfg["connection"] == "nbiot" and not self.lte.isconnected():
                import nb_iot
                pycom.rgbled(0x440044)
                self.log_and_print("!! lost NB-IoT connection, trying to reconnect ...")
                if not nb_iot.connect(self.lte):
                    self.log_and_print("ERROR: unable to connect to network. Resetting device...")
                    time.sleep(5)
                    machine.reset()
                else:
                    pycom.rgbled(0x002200)

            # send data to ubirch data service and certificate to ubirch auth service
            try:
                self.ubirch_data.send(data)
            except Exception as e:
                pycom.rgbled(0x440000)
                logger.exception(e)
                with open('log.txt', 'a') as logfile:
                    logfile.write("{}: {}\n".format(str(rtc.now()), repr(e)))
                time.sleep(2)

            print("** done.\n")
            passed_time = time.time() - start_time
            if interval > passed_time:
                pycom.rgbled(0)
                time.sleep(interval - passed_time)


main = Main()
main.loop(60)
