import json
import time
from uuid import UUID

import machine
# Pycom specifics
import pycom
from pyboard import Pysense, Pytrack, Pycoproc
# ubirch data client
from ubirch import UbirchDataClient

# load configuration from config.json file
# the config.json should be placed next to this file
# {
#  "type": "<TYPE: 'pysense' or 'pytrack'>",
#  "password": "<password for ubirch auth and data service>",
#  "keyService": "<URL of key registration service>",
#  "niomon": "<URL of authentication service>",
#  "data": "<URL of data service>",
# }
with open('config.json', 'r') as c:
    cfg = json.load(c)
rtc = machine.RTC()

class Main:
    """
    |  UBIRCH example for pycom modules.
    |
    |  The devices creates a unique UUID and sends data to the ubirch data service.
    |  At the initial start these steps are required:
    |
    |  - start the pycom module with this code
    |  - take note of the UUID printed on the serial console
    |  - go to 'https://console.dev.ubirch.com/' and register your device
    |
    """

    def __init__(self) -> None:

        # generate UUID
        self.uuid = UUID(b'UBIR'+ 2*machine.unique_id())
        print("\n** UUID   : " + str(self.uuid) + "\n")

        # ubirch data client for setting up ubirch protocol, authentication and data service
        self.ubirch_data = UbirchDataClient(self.uuid, cfg)

        # initialize the sensor based on the type of the pycom add-on board
        if cfg["type"] == "pysense":
            self.sensor = Pysense()
        elif cfg["type"] == "pytrack":
            self.sensor = Pytrack()
        else:
            print("board type not supported.")

    def prepare_data(self):
        """
        Prepare the data from the sensor module and return it in the format we need.
        :return: a dictionary (json) with the data
        """

        data = {
            "type": cfg["type"]
        }

        if isinstance(self.sensor, Pysense) or isinstance(self.sensor, Pytrack):
            accel = self.sensor.accelerometer.acceleration()
            roll = self.sensor.accelerometer.roll()
            pitch = self.sensor.accelerometer.pitch()

            data.update({
                "Acc": {
                    "xyz": accel,
                    "roll": roll,
                    "pitch": pitch
                }
            })

        if isinstance(self.sensor, Pysense):
            data.update({
                "T": self.sensor.barometer.temperature(),
                "P": self.sensor.barometer.pressure(),
                "H": self.sensor.humidity.humidity(),
                "L": self.sensor.light()
            })

        if isinstance(self.sensor, Pytrack):
            data.update({
                "GPS": self.sensor.location.coordinates()
            })

        if isinstance(self.sensor, Pycoproc):
            data.update({
                "V": self.sensor.voltage()
            })

        return data

    def loop(self, interval: int = 60):
        # disable blue heartbeat blink
        pycom.heartbeat(False)
        while True:
            pycom.rgbled(0x112200)
            print("\n** getting measurements:")
            data = self.prepare_data()
            print(json.dumps(data))

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
main.loop(10)
