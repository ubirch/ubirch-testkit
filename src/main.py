import logging
import machine
import os
import sys
import time
import ubinascii
from uuid import UUID
from connection import WIFI, NB_IoT

# Pycom specifics
import pycom
from pyboard import Pysense, Pytrack

# Ubirch client
from ubirch import UbirchClient
from config import get_config

logger = logging.getLogger(__name__)

rtc = machine.RTC()

LED_GREEN = 0x002200
LED_YELLOW = 0x7f7f00
LED_RED = 0x7f0000
LED_PURPLE = 0x7f007f

MAX_FILE_SIZE = 10000  # in bytes


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

        # generate UUID
        self.uuid = UUID(b'UBIR' + 2 * machine.unique_id())
        print("\n** UUID   : " + str(self.uuid))
        print("** MAC    : " + ubinascii.hexlify(machine.unique_id(), ':').decode() + "\n")

        try:
            # mount SD card (operation throws exception if no SD card present)
            sd = machine.SD()
            os.mount(sd, '/sd')
            # write UUID to file on SD card if file doesn't already exist
            uuid_file = "uuid.txt"
            if uuid_file not in os.listdir('/sd'):
                with open('/sd/' + uuid_file, 'w') as f:
                    f.write(str(self.uuid))
        except OSError:
            print("!! writing UUID to SD card failed")
            pycom.heartbeat(False)
            pycom.rgbled(LED_YELLOW)
            time.sleep(3)
            pycom.heartbeat(True)

        # load configuration from file (raises exception if file can't be found)
        self.cfg = get_config()
        if self.cfg['debug']:
            print("** loaded configuration:\n{}\n".format(self.cfg))

        # set up logging to file
        if self.cfg['logfile']:
            # set up error logging to log file
            self.logfile_name = 'log.txt'
            with open(self.logfile_name, 'a') as f:
                self.file_position = f.tell()
            print(
                "** file logging enabled. log file: {}, size: {:.1f} kb, free flash memory: {:d} kb\n".format(
                    self.logfile_name, self.file_position / 1000.0, os.getfree('/flash')))

        # connect to network
        try:
            if self.cfg['connection'] == "wifi":
                self.connection = WIFI(self.cfg['networks'])
            elif self.cfg['connection'] == "nbiot":
                self.connection = NB_IoT(self.cfg['apn'])
            else:
                raise Exception("Connection type {} not supported. Supported types: 'wifi' and 'nbiot'".format(
                    self.cfg["connection"]))
        except ConnectionError as e:
            self.report(repr(e) + " Resetting device...", LED_PURPLE)
            machine.reset()

        # initialize the sensor based on the type of the Pycom expansion board
        if self.cfg["type"] == "pysense":
            self.sensor = Pysense()
        elif self.cfg["type"] == "pytrack":
            self.sensor = Pytrack()
        else:
            raise Exception("Expansion board type {} not supported. Supported types: 'pysense' and 'pytrack'".format(
                self.cfg["type"]))

        # initialise ubirch client for setting up ubirch protocol, authentication and data service
        try:
            self.ubirch_client = UbirchClient(self.uuid, self.cfg)
        except Exception as e:
            self.report("!! initialisation failed. " + repr(e) + " Resetting device...", LED_RED)
            machine.reset()

    def report(self, error: str or Exception, led_color: int):
        pycom.heartbeat(False)
        pycom.rgbled(led_color)
        if isinstance(error, Exception):
            sys.print_exception(error)
        else:
            print(error)
        if self.cfg['logfile']: self.log_to_file(error)
        time.sleep(3)

    def log_to_file(self, error: str or Exception):
        with open(self.logfile_name, 'a') as f:
            # start overwriting oldest logs once file reached its max size
            # issue: once file reached its max size, file position will always be set to beginning after device reset
            if self.file_position > MAX_FILE_SIZE:
                self.file_position = 0
            # set file to recent position
            f.seek(self.file_position, 0)

            # log error message and traceback if error is an exception
            t = rtc.now()
            f.write('({:04d}.{:02d}.{:02d} {:02d}:{:02d}:{:02d}) '.format(t[0], t[1], t[2], t[3], t[4], t[5]))
            if isinstance(error, Exception):
                sys.print_exception(error, f)
            else:
                f.write(error + "\n")

            # remember current file position
            self.file_position = f.tell()

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
