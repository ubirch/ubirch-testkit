import os
import time
import machine
import json
from uuid import UUID

# Pycom specifics
import pycom
from pyboard import Pysense, Pytrack, Pycoproc

# ubirch client (handles protocol and communication)
from ubirch import UbirchClient

# Cumulocity API
from c8y.http_client import C8yHTTPClient as C8yClient

# load configuration from settings.json file
# the settings.json should be placed next to this file
# {
#  "type": "<TYPE: 'pysense' or 'pytrack'>",
#  "bootstrap": {
#     "authorization": "Basic <base64 bootstrap auth>",
#     "tenant": "<tenant>",
#     "host": "management.cumulocity.com"
#   }
# }
with open('settings.json', 'r') as c:
    cfg = json.load(c)
rtc = machine.RTC()

class Main:
    """
    |  UBIRCH example for pycom modules.
    |
    |  The devices creates a unique UUID and then registers the device
    |  at the cumulocity tenant configured in settings.json.
    |  After the initial start these steps are required:
    |
    |  - start the pycom module with this code
    |  - take note of the UUID printed on the serial console
    |  - go to 'tenant.cumulocity.com' and register your devices
    |  - after the connection is recognized, accept the device
    |
    |  The device stores its credentials automatically and will use
    |  them from then on.
    """

    def __init__(self) -> None:
        # disable blue heartbeat blink
        pycom.heartbeat(False)

        # set up ubirch protocol
        self.uuid = UUID(b'UBIR'+ 2*machine.unique_id())
        print("** UUID   : "+str(self.uuid))

        # create Cumulocity client (bootstraps)
        uname = os.uname()
        self.c8y = C8yClient(self.uuid, dict(cfg['bootstrap']), {
            "name": str(self.uuid),
            "c8y_IsDevice": {},
            "c8y_Hardware": {
                "model": uname.machine + "-" + cfg['type'],
                "revision": uname.release + "-" + uname.version,
                "serialNumber": str(self.uuid)
            }
        })
        self.ubirch = UbirchClient(self.uuid, cfg.get("env", "dev"))

        # initialize the sensor based on the type of the pycom add-on board
        if cfg["type"] == "pysense":
            self.sensor = Pysense()
        elif cfg["type"] == "pytrack":
            self.sensor = Pytrack()

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
                "c8y_TemperatureSensor": {
                    "T": {"value": self.sensor.barometer.temperature(), "unit": "C"},
                },
                "c8y_HumidityMeasurement": {
                    "H": {"value": self.sensor.humidity.humidity(), "unit": "%RH"},
                    "T": {"value": self.sensor.humidity.temperature(), "unit": "C"},
                    "D": {"value": self.sensor.humidity.dew_point(), "unit": "C"}
                },
                "c8y_PressureMeasurement": {
                    "P": {"value": self.sensor.barometer.pressure(), "unit": "Pa"},
                    "T": {"value": self.sensor.barometer.temperature(), "unit": "C"}
                },
                "c8y_LightMeasurement": {
                    "B": {"value": self.sensor.light()[0], "unit": "lux"},
                    "R": {"value": self.sensor.light()[1], "unit": "lux"}
                }
            })

        if isinstance(self.sensor, Pysense) or isinstance(self.sensor, Pytrack):
            accel = self.sensor.accelerometer.acceleration()
            roll = self.sensor.accelerometer.roll()
            pitch = self.sensor.accelerometer.pitch()

            data.update({
                "c8y_AccelerationMeasurement": {
                    "x": {"value": accel[0], "unit": "m/s2"},
                    "y": {"value": accel[1], "unit": "m/s2"},
                    "z": {"value": accel[2], "unit": "m/s2"},
                    "roll": {"value": roll, "unit": "d"},
                    "pitch": {"value": pitch, "unit": "d"}
                },
            })


            if isinstance(self.sensor, Pycoproc):
                data.update({
                    "c8y_VoltageMeasurement": {
                        "voltage": {"value": self.sensor.voltage(), "unit": "V"}
                    }
                })

        return data

    def loop(self, interval: int = 60):
        while True:
            pycom.rgbled(0x001100)
            data = self.prepare_data()

            print(json.dumps(data))
            # send data to Cumulocity
            try:
                print("** sending measurements ...")
                self.c8y.measurement(data)
            except Exception as e:
                pycom.rgbled(0x110000)
                print("!! error sending data to backend: "+repr(e))
                time.sleep(2)
            else:
                pycom.rgbled(0x001100)

            # send data certificate (UPP) to UBIRCH
            try:
                print("** sending measurement certificate ...")
                (upp, r) = self.ubirch.send(data)
            except Exception as e:
                pycom.rgbled(0x440000)
                print("!! response: verification failed: {}".format(e))
                time.sleep(2)
            else:
                if r.status_code != 202:
                    pycom.rgbled(0x550000)
                    print("!! request failed with {}: {}".format(r.status_code, r.content.decode()))
                    time.sleep(2)

            # everything okay
            pycom.rgbled(0x004400)
            print("** done")

            time.sleep(interval)


print("** ubirch-protocol example v1.0")
main = Main()
main.loop()
