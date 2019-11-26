import json
import logging
import time
from uuid import UUID

import machine
# Pycom specifics
import pycom
import wifi
from pyboard import Pysense, Pytrack
# ubirch data client
from ubirch import UbirchDataClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from wifi import set_time


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

        if self.cfg["connection"] == "wifi":
            # try to connect via wifi, throws exception if no success
            wifi.connect(self.cfg['networks'])
            set_time()  # fixme doesnt set time with nbiot
            # wlan = WLAN(mode=WLAN.STA)
        elif self.cfg["connection"] == "nbiot":
            from nb_iot_client import NbIotClient
            self.nbiot = NbIotClient(self.uuid, self.cfg)

        # ubirch data client for setting up ubirch protocol, authentication and data service
        self.ubirch_data = UbirchDataClient(self.uuid, self.cfg)

        # initialize the sensor based on the type of the pycom add-on board
        if self.cfg["type"] == "pysense":
            self.sensor = Pysense()
        elif self.cfg["type"] == "pytrack":
            self.sensor = Pytrack()
        else:
            logger.error("Expansion board type not supported. This version supports types \"pysense\" and \"pytrack\"")

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
            pycom.rgbled(0x112200)

            # make sure device is still connected
            # if not wlan.isconnected():
            #     logger.warning("!! lost wifi connection, trying to reconnect ...")
            #     wifi.connect(self.cfg['networks'])

            # get data
            print("** getting measurements:")
            data = self.prepare_data()
            self.print_data(data)

            # send data to ubirch data service and certificate to ubirch auth service
            try:
                self.ubirch_data.send(data)
            except Exception as e:
                pycom.rgbled(0x440000)
                logger.exception(e)
                time.sleep(2)

            print("** done.\n")
            passed_time = time.time() - start_time
            if interval > passed_time:
                pycom.rgbled(0)
                time.sleep(interval - passed_time)


main = Main()
main.loop(60)
