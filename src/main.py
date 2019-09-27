import json
import time
from uuid import UUID

import machine
# Pycom specifics
import pycom
from pyboard import Pysense, Pytrack
# ubirch data client
from ubirch import UbirchDataClient

rtc = machine.RTC()

setup_help_text = """
* Copy the UUID and register your device at the Ubirch Web UI: https://console.demo.ubirch.com\n
* Then, create a file \"config.json\" next to main.py and paste the apiConfig into it.\n
* Upload the file to your device and run again.\n\n
For more information, take a look at the README.md of this repository.
"""

class Main:
    """
    |  UBIRCH example for pycom modules.
    |
    |  The devices creates a unique UUID and sends data to the ubirch data and auth service.
    |  At the initial start these steps are required:
    |
    |  - start the pycom module with this code
    |  - take note of the UUID printed on the serial console
    |  - go to 'https://console.demo.ubirch.com/' and register your device
    |
    """

    def __init__(self) -> None:

        # generate UUID
        self.uuid = UUID(b'UBIR'+ 2*machine.unique_id())
        print("\n** UUID   : " + str(self.uuid) + "\n")

        # load configuration from config.json file
        # the config.json should be placed next to this file
        # {
        #  "type": "<TYPE: 'pysense' or 'pytrack'>",
        #  "password": "<password for ubirch auth and data service>",
        #  "keyService": "<URL of key registration service>",
        #  "niomon": "<URL of authentication service>",
        #  "data": "<URL of data service>",
        # }
        try:
            with open('config.json', 'r') as c:
                cfg = json.load(c)
        except OSError:
            print(setup_help_text)
            while True:
                time.sleep(60)

        # ubirch data client for setting up ubirch protocol, authentication and data service
        self.ubirch_data = UbirchDataClient(self.uuid, cfg)

        # initialize the sensor based on the type of the pycom add-on board
        if cfg["type"] == "pysense":
            self.sensor = Pysense()
        elif cfg["type"] == "pytrack":
            self.sensor = Pytrack()
        else:
            print("Expansion board type not supported.\nThis version supports the types \"pysense\" and \"pytrack\"")

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

    def printData(self, data: dict):
        print("{")
        for key in sorted(data):
            print("  \"{}\": {},".format(key, data[key]))
        print("}")


    def loop(self, interval: int = 60):
        # disable blue heartbeat blink
        pycom.heartbeat(False)
        while True:
            pycom.rgbled(0x112200)
            print("\n** getting measurements:")
            data = self.prepare_data()
            self.printData(data)

            # send data to data service and ubirch protocol package (UPP) with hash over data to ubirch backend
            try:
                self.ubirch_data.send(data)
            except Exception as e:
                pycom.rgbled(0x440000)
                print(e)
                time.sleep(2)

            pycom.rgbled(0x110022)
            print("** done. going to sleep ...")
            time.sleep(interval)


main = Main()
main.loop(30)
