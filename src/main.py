import sys
import time

import machine
# Pycom specifics
import pycom
import ubinascii as binascii

from config import get_config
from connection import get_connection, NB_IoT
from file_logging import FileLogger, LED_GREEN, LED_YELLOW, LED_ORANGE, LED_RED, LED_PURPLE
from pyboard import Pyboard
# ubirch client
from ubirch import UbirchClient


def sleep_until_next_interval(start_time, interval):
    passed_time = time.time() - start_time
    if interval > passed_time:
        print("\n** going to sleep...\n")
        pycom.rgbled(0)  # LED off
        time.sleep(interval - passed_time)


def wake_up():
    pycom.rgbled(LED_GREEN)
    return time.time()


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

    def __init__(self):
        print("\n** MAC    : " + binascii.hexlify(machine.unique_id(), ':').decode() + "\n")

        # load configuration
        try:
            self.cfg = get_config()
        except Exception as e:
            self.report(e, LED_YELLOW)
            while True:
                machine.idle()

        print("** configuration:\n{}\n".format(self.cfg))

        # connect to network
        try:
            self.connection = get_connection(self.cfg)
        except OSError as e:
            self.report(repr(e) + " Resetting device...", LED_PURPLE, reset=True)

        # set up logging to file
        if self.cfg['logfile']: self.logfile = FileLogger()

        # initialize the sensors
        self.sensor = Pyboard(self.cfg['board'])

        # initialise ubirch client
        try:
            self.ubirch_client = UbirchClient(self.cfg, lte=self.connection.lte)
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
        if self.cfg['logfile']: self.logfile.log(error)
        if reset:
            time.sleep(5)
            machine.reset()

    def loop(self):
        # disable blue heartbeat blink
        pycom.heartbeat(False)
        print("** starting loop... (interval = {} seconds)\n".format(self.cfg['interval']))
        while True:
            start_time = wake_up()

            # get data
            print("** getting measurements:")
            data = self.sensor.get_data()
            self.sensor.print_data(data)

            # make sure device is still connected or reconnect
            if not self.connection.is_connected() and not self.connection.connect():
                self.report("!! unable to connect to network. Resetting device...", LED_PURPLE, reset=True)

            # send data to ubirch data service and certificate to ubirch auth service
            try:
                self.ubirch_client.send(data)
            except Exception as e:
                self.report(e, LED_ORANGE)
                if isinstance(e, OSError):
                    machine.reset()

            # LTE stops working after a while, so we disconnect after sending
            # and reconnect again in the next interval to make sure it still works
            if isinstance(self.connection, NB_IoT):
                self.connection.disconnect()

            sleep_until_next_interval(start_time, self.cfg['interval'])


main = Main()
main.loop()
