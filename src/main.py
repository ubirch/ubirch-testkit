import logging
import machine
import os
import sys
import time
import ubinascii

from file_logging import Logfile
from uuid import UUID
from config import get_config

# Pycom specifics
import pycom
from pyboard import Pysense, Pytrack

logger = logging.getLogger(__name__)

LED_GREEN = 0x002200
LED_YELLOW = 0x7f7f00
LED_RED = 0x7f0000
LED_PURPLE = 0x220022


def pretty_print_data(data: dict):
    print("{")
    for key in sorted(data):
        print("  \"{}\": {},".format(key, data[key]))
    print("}\n")


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

        # load configuration from file (raises exception if configuration is missing)
        self.cfg = get_config()
        if self.cfg['debug']:
            print("** loaded configuration:\n{}\n".format(self.cfg))

        print("** MAC    : " + ubinascii.hexlify(machine.unique_id(), ':').decode() + "\n")

        # generate UUID if no SIM is used (otherwise UUID shall ne retrieved from SIM)   todo rearrange
        if not self.cfg['sim']:
            self.uuid = UUID(b'UBIR' + 2 * machine.unique_id())
            print("** UUID   : " + str(self.uuid) + "\n")

            # write UUID to file on SD card if file doesn't already exist
            try:
                sd = machine.SD()  # sd is already mounted in get_config() todo make sure it really is!
                uuid_file = "uuid.txt"
                if uuid_file not in os.listdir('/sd'):
                    with open('/sd/' + uuid_file, 'w') as f:
                        f.write(str(self.uuid))
                sd.deinit()
            except OSError as e:
                self.report("writing UUID to SD card failed. " + repr(e), LED_YELLOW)
                pycom.heartbeat(True)

        # set debug level
        if self.cfg['debug']:
            logging.basicConfig(level=logging.DEBUG)

        # set up logging to file
        if self.cfg['logfile']:
            self.logfile = Logfile()

        # connect to network
        try:
            if self.cfg['connection'] == "wifi":
                from connection import WIFI
                from network import WLAN
                wlan = WLAN(mode=WLAN.STA)
                self.connection = WIFI(wlan, self.cfg['networks'])
            elif self.cfg['connection'] == "nbiot":
                from connection import NB_IoT
                if not hasattr(self, 'lte'):
                    from network import LTE
                    self.lte = LTE()
                self.connection = NB_IoT(self.lte, self.cfg['apn'])
            else:
                raise Exception("Connection type {} not supported. Supported types: 'wifi' and 'nbiot'".format(
                    self.cfg['connection']))
        except OSError as e:
            self.report(repr(e) + " Resetting device...", LED_PURPLE)
            machine.reset()

        # initialize the sensor based on the type of the Pycom expansion board
        if self.cfg['type'] == "pysense":
            self.sensor = Pysense()  # todo throws OSError: I2C bus error when trying to initialise wrong board
        elif self.cfg['type'] == "pytrack":
            self.sensor = Pytrack()
        else:
            raise Exception("Expansion board type {} not supported. Supported types: 'pysense' and 'pytrack'".format(
                self.cfg['type']))

        # initialise ubirch client
        try:
            if self.cfg['sim']:
                from ubirch import UbirchSimClient
                device_name = "A"
                if not hasattr(self, 'lte'):
                    from network import LTE
                    self.lte = LTE()
                self.ubirch_client = UbirchSimClient(device_name, self.cfg, self.lte)
            else:
                from ubirch import UbirchClient
                self.ubirch_client = UbirchClient(self.uuid, self.cfg)
        except Exception as e:
            self.report(e, LED_RED)
            self.report(" Resetting device...", LED_PURPLE)
            machine.reset()

    def report(self, error: str or Exception, led_color: int):
        pycom.heartbeat(False)
        pycom.rgbled(led_color)
        if isinstance(error, Exception):
            sys.print_exception(error)
        else:
            print(error)
        if self.cfg['logfile']: self.logfile.log(error)
        time.sleep(3)

    def prepare_data(self) -> dict:
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

    def loop(self):
        # disable blue heartbeat blink
        pycom.heartbeat(False)
        print("** starting loop... (interval = {} seconds)\n".format(self.cfg["interval"]))
        while True:
            start_time = time.time()
            pycom.rgbled(LED_GREEN)

            # get data
            print("** getting measurements:")
            data = self.prepare_data()
            pretty_print_data(data)

            # make sure device is still connected
            if not self.connection.is_connected():
                if not self.connection.connect():
                    self.report("!! unable to connect to network. Resetting device...", LED_PURPLE)
                    machine.reset()
                else:
                    pycom.rgbled(LED_GREEN)

            # send data to ubirch data service and certificate to ubirch auth service
            try:
                self.ubirch_client.send(data)
            except Exception as e:
                self.report(e, LED_RED)
                if isinstance(e, OSError):
                    machine.reset()

            # LTE stops working after a while, so we disconnect after sending and reconnect to make sure it works
            # if connection is a WIFI instance, this method call does nothing (WIFI stays connected all the time)
            self.connection.disconnect()

            print("** done.\n")
            passed_time = time.time() - start_time
            if self.cfg['interval'] > passed_time:
                pycom.rgbled(0)  # LED off
                time.sleep(self.cfg['interval'] - passed_time)


main = Main()
main.loop()
