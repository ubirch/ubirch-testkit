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

# load configuration from settings.json file
# the settings.json should be placed next to this file
# {
#  "type": "<TYPE: 'pysense' or 'pytrack'>",
#  "auth": "<password for ubirch data service>",
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
        # disable blue heartbeat blink
        pycom.heartbeat(False)

        # generate UUID
        self.uuid = UUID(b'UBIR'+ 2*machine.unique_id())
        print("** UUID   : "+str(self.uuid))

        self.ubirch_data = UbirchDataClient(self.uuid, cfg)

        # initialize the sensor based on the type of the pycom add-on board
        if cfg["type"] == "pysense":
            self.sensor = Pysense()
        elif cfg["type"] == "pytrack":
            self.sensor = Pytrack()
        elif cfg["type"] == "pycoproc":
            self.sensor = Pycoproc()
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

        if isinstance(self.sensor, Pysense):
            data.update({
                "TemperatureSensor": {
                    "T": {"value": self.sensor.barometer.temperature(), "unit": "C"},
                },
                "HumidityMeasurement": {
                    "H": {"value": self.sensor.humidity.humidity(), "unit": "%RH"},
                    "T": {"value": self.sensor.humidity.temperature(), "unit": "C"},
                    "D": {"value": self.sensor.humidity.dew_point(), "unit": "C"}
                },
                "PressureMeasurement": {
                    "P": {"value": self.sensor.barometer.pressure(), "unit": "Pa"},
                    "T": {"value": self.sensor.barometer.temperature(), "unit": "C"}
                },
                "LightMeasurement": {
                    "B": {"value": self.sensor.light()[0], "unit": "lux"},
                    "R": {"value": self.sensor.light()[1], "unit": "lux"}
                }
            })

        if isinstance(self.sensor, Pysense) or isinstance(self.sensor, Pytrack):
            accel = self.sensor.accelerometer.acceleration()
            roll = self.sensor.accelerometer.roll()
            pitch = self.sensor.accelerometer.pitch()

            data.update({
                "AccelerationMeasurement": {
                    "x": {"value": accel[0], "unit": "m/s2"},
                    "y": {"value": accel[1], "unit": "m/s2"},
                    "z": {"value": accel[2], "unit": "m/s2"},
                    "roll": {"value": roll, "unit": "d"},
                    "pitch": {"value": pitch, "unit": "d"}
                },
            })


            if isinstance(self.sensor, Pycoproc):
                data.update({
                    "VoltageMeasurement": {
                        "voltage": {"value": self.sensor.voltage(), "unit": "V"}
                    }
                })

        return data

    def loop(self, interval: int = 60):
        from breathe import Breathe
        sleep_indicator = Breathe()
        while True:
            pycom.rgbled(0x001100)
            data = self.prepare_data()

            print(json.dumps(data))

            # send data to ubirch data service
            try:
                print("** sending data point to ubirch data service ...")
                self.ubirch_data.send(self.sensor.light()[0])
            except Exception as e:
                pycom.rgbled(0x110000)
                print("!! error sending data to ubirch data service: "+repr(e))
                time.sleep(2)

            pycom.rgbled(0x004400)
            print("** done")

            sleep_indicator.start()
            time.sleep(interval)
            sleep_indicator.stop()


main = Main()
main.loop(5)
