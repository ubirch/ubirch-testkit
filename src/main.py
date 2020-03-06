import logging
import machine
import os
import sys
import time
import ubinascii
import ujson as json
from config import Config
from connection import Connection, NB_IoT
from file_logging import Logfile
from uuid import UUID

# Pycom specifics
import pycom
from pyboard import Pyboard

logger = logging.getLogger(__name__)

LED_GREEN = 0x002200
LED_YELLOW = 0x444400
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

        # load configuration from file
        self.cfg = Config()

        print("\n** MAC    : " + ubinascii.hexlify(machine.unique_id(), ':').decode() + "\n")

        # generate UUID if no SIM is used (otherwise UUID shall be retrieved from SIM)
        if not self.cfg.sim:
            self.uuid = UUID(b'UBIR' + 2 * machine.unique_id())
            print("** UUID   : " + str(self.uuid) + "\n")

            if SD_CARD_MOUNTED:
                # write UUID to file on SD card if file doesn't already exist
                uuid_file = "uuid.txt"
                if uuid_file not in os.listdir('/sd'):
                    with open('/sd/' + uuid_file, 'w') as f:
                        f.write(str(self.uuid))

        # check if ubirch backend password is already known. If unknown, look for it on SD card.
        if self.cfg.password is None:
            api_config_file = 'config.txt'
            # get config from SD card
            if SD_CARD_MOUNTED and api_config_file in os.listdir('/sd'):
                with open('/sd/' + api_config_file, 'r') as f:
                    api_config = json.load(f)  # todo what if password still not in config?
            else:
                self.report("!! missing password", LED_YELLOW)  # todo document what yellow LED means for user
                while True:
                    machine.idle()

            # add API config from SD card to existing config
            self.cfg.set_api_config(api_config)
            # print("** configuration:\n{}\n".format(self.cfg)) todo print config

        # set debug level
        if self.cfg.debug:
            logging.basicConfig(level=logging.DEBUG)

        # set up logging to file
        if self.cfg.logfile:
            self.logfile = Logfile()

        # connect to network
        try:
            self.connection = Connection(self.cfg)
        except OSError as e:
            self.report(repr(e) + " Resetting device...", LED_PURPLE, reset=True)

        # initialize the sensors
        self.sensor = Pyboard()

        # initialise ubirch client
        try:
            if self.cfg.sim:
                from ubirch import UbirchSimClient
                device_name = "A"
                self.ubirch_client = UbirchSimClient(device_name, self.cfg, self.connection.lte)
            else:
                from ubirch import UbirchClient
                self.ubirch_client = UbirchClient(self.uuid, self.cfg)
        except Exception as e:
            self.report(e, LED_RED)
            self.report("!! Initialisation failed. Resetting device...", LED_RED, reset=True)

    def report(self, error: str or Exception, led_color: int, reset: bool = False):
        pycom.heartbeat(False)
        pycom.rgbled(led_color)
        if isinstance(error, Exception):
            sys.print_exception(error)
        else:
            print(error)
        if self.cfg.logfile: self.logfile.log(error)
        if reset:
            time.sleep(5)
            machine.reset()

    def loop(self):
        # disable blue heartbeat blink
        pycom.heartbeat(False)
        print("** starting loop... (interval = {} seconds)\n".format(self.cfg.interval))
        while True:
            start_time = time.time()
            pycom.rgbled(LED_GREEN)

            # get data
            print("** getting measurements:")
            data = self.sensor.get_data()
            pretty_print_data(data)

            # make sure device is still connected
            if not self.connection.is_connected() and not self.connection.connect():  # todo check if its safe to do this in one line
                self.report("!! unable to connect to network. Resetting device...", LED_PURPLE, reset=True)

            # send data to ubirch data service and certificate to ubirch auth service
            try:
                self.ubirch_client.send(data)
            except Exception as e:
                self.report(e, LED_RED)
                if isinstance(e, OSError):
                    machine.reset()

            # LTE stops working after a while, so we disconnect after sending
            # and reconnect again in the next interval to make sure it still works
            if isinstance(self.connection, NB_IoT):
                self.connection.disconnect()

            print("** done.\n")
            passed_time = time.time() - start_time
            if self.cfg.interval > passed_time:
                pycom.rgbled(0)  # LED off
                time.sleep(self.cfg.interval - passed_time)


main = Main()
main.loop()
