import os
import time
import machine
import json
from uuid import UUID

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
        print("** UUID   : "+str(self.uuid))

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

        ts = rtc.now()
        timestamp_str = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}.{:03d}Z".format(
            ts[0], ts[1], ts[2], ts[3], ts[4], ts[5], ts[6] // 1000
        )

        data = {
            "time": timestamp_str,
            "type": cfg["type"]
        }

        if isinstance(self.sensor, Pysense) or isinstance(self.sensor, Pytrack):
            accel = self.sensor.accelerometer.acceleration()
            roll = self.sensor.accelerometer.roll()
            pitch = self.sensor.accelerometer.pitch()

            data.update({
                "Accelerometer": {
                    "X-axis": {"value": accel[0], "unit": "g"},
                    "Y-axis": {"value": accel[1], "unit": "g"},
                    "Z-axis": {"value": accel[2], "unit": "g"},
                    "Roll": {"value": roll, "unit": "deg"},
                    "Pitch": {"value": pitch, "unit": "deg"}
                },
            })

        if isinstance(self.sensor, Pysense):
            data.update({
                "HumiditySensor": {
                    "Humidity": {"value": self.sensor.humidity.humidity(), "unit": "%RH"},
                    "Temperature": {"value": self.sensor.humidity.temperature(), "unit": "C"},
                    "DewPoint": {"value": self.sensor.humidity.dew_point(), "unit": "C"}
                },
                "Barometer": {
                    "Pressure": {"value": self.sensor.barometer.pressure(), "unit": "Pa"},
                    "Temperature": {"value": self.sensor.barometer.temperature(), "unit": "C"}
                },
                "LightSensor": {
                    "Blue": {"value": self.sensor.light()[0], "unit": "lux"},
                    "Red": {"value": self.sensor.light()[1], "unit": "lux"}
                }
            })

        if isinstance(self.sensor, Pytrack):
            data.update({
                "Location": {
                    "Longitude": {"value": self.sensor.location.coordinates()[0], "unit": "deg"},
                    "Latitude": {"value": self.sensor.location.coordinates()[1], "unit": "deg"}
                }
            })

        if isinstance(self.sensor, Pycoproc):
            data.update({
                "Voltage": {"value": self.sensor.voltage(), "unit": "V"}
            })

        return data

    def loop(self, interval: int = 60):
        # disable blue heartbeat blink
        pycom.heartbeat(False)
        while True:
            pycom.rgbled(0x112200)
            print("** getting measurements.")
            data = self.prepare_data()
            print("\"data\": " + json.dumps(data))

            # send data to ubirch data service
            try:
                self.ubirch_data.send(data)
            except Exception as e:
                pycom.rgbled(0x440000)
                print("!! error sending data to ubirch data service: "+repr(e))
                time.sleep(2)

            pycom.rgbled(0x110022)
            print("** done. going to sleep...")
            time.sleep(interval)


main = Main()
main.loop(10)
