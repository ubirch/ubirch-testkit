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

# azure client
from azure import AzureClient

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
        self.ubirch = UbirchClient(self.uuid, self.c8y.get_auth(), cfg.get("env", "dev"))

        # create Azure client (MQTT) and establish connection
        self.azure = AzureClient()
        self.azure.connect()

        # initialize the sensor based on the type of the pycom add-on board
        if cfg["type"] == "pysense":
            self.sensor = Pysense()
        elif cfg["type"] == "pytrack":
            self.sensor = Pytrack()

    def prepare_data(self, value):
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
        if (value == 1):
            data.update({
                "c8y_PouringCoffeee": {
                    "coffee": {"value": value, "unit": "coffee"}
                }
            })

        else:
            data.update({
                "c8y_VoltageMeasurement": {
                    "voltage": {"value": self.sensor.voltage(), "unit": "V"}
                }
            })

        return data

    def send(self, data):
        # send data to Cumulocity
        try:
            print("** sending measurements to Cumulocity...")
            self.c8y.measurement(data)
        except Exception as e:
            pycom.rgbled(0x110000)
            print("!! error sending data to backend: "+repr(e))
            time.sleep(2)
        else:
            pycom.rgbled(0x001100)

        # send data to Azure IoT hub
        try:
            print("** sending measurements to Azure...")
            self.azure.send(json.dumps(data))
        except Exception as e:
            pycom.rgbled(0x110000)
            print("!! error sending data to IoT hub: "+repr(e))
            time.sleep(2)

        # send data certificate (UPP) to UBIRCH
        try:
            print("** sending measurement certificate ...")
            (response, r) = self.ubirch.send(data)
        except Exception as e:
            pycom.rgbled(0x440000)
            print("!! response: verification failed: {}".format(e))
            time.sleep(2)
        else:
            if r.status_code != 200:
                pycom.rgbled(0x550000)
                print("!! request failed with {}: {}".format(r.status_code, r.content.decode()))
                time.sleep(2)
            else:
                print(response)
                if isinstance(response, dict):
                    interval = response.get("i", interval)


        # everything okay
        pycom.rgbled(0x004400)
        print("** done")
        return True

    def loop(self, interval: int = 60):
        from breathe import Breathe
        sleep_indicator = Breathe()
        data_time = 0
        last_coffee = 0
        avg_roll = self.sensor.accelerometer.roll()
        while True:
            pycom.rgbled(0x001100)
            pitch = self.sensor.accelerometer.pitch()
            roll = self.sensor.accelerometer.roll()
            print("** pitch: " + str(pitch))
            print("** roll: " + str(roll))

            # detect coffee
            if (abs(avg_roll - roll) > 20 ):
                data = self.prepare_data(1)
                print(json.dumps(data))

                # avoid duplicates
                if (data_time < 5 or data_time - last_coffee > 5):
                    # print("should send data")
                    self.send(data)
                else:
                    print("already had a coffee recently, you silly!")

                last_coffee = data_time

            if (data_time > 30):
                avg_roll = ((avg_roll*30) + roll ) / (30 + 1)
            else:
                avg_roll = ((avg_roll*data_time) + roll ) / (data_time + 1)


            # ping
            if (data_time % 100 == 0):
                data = self.prepare_data(0)
                print(json.dumps(data))
                self.send(data)

            sleep_indicator.start()
            time.sleep(interval)
            sleep_indicator.stop()
            data_time = data_time + 1
            print("** avg_roll: " + str(avg_roll))


print("** ubirch-protocol coffee machine v1.0")
main = Main()
main.loop(2)
