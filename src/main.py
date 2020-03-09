import machine
import os
import time
import sys
from connection import Connection, NB_IoT
from file_logging import FileLogger, LED_GREEN, LED_RED, LED_YELLOW, LED_PURPLE
import ubirch
from uuid import UUID

# Pycom specifics
import pycom
from pyboard import Pyboard


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

        # set up logging to file
        if CFG.logfile:
            self.logfile = FileLogger()

        # initialize the sensors
        self.sensor = Pyboard()

        # connect to network
        try:
            self.connection = Connection(CFG)
        except OSError as e:
            self.report(repr(e) + " Resetting device...", LED_PURPLE, reset=True)

        # initialise ubirch client
        try:
            if CFG.sim:
                from ubirch.ubirch_sim_client import UbirchSimClient
                self.ubirch_client = UbirchSimClient(CFG, self.connection.lte)
            else:
                from ubirch.ubirch_protocol_client import UbirchProtocolClient
                self.ubirch_client = UbirchProtocolClient(PYCOM_UUID)
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
        if CFG.logfile: self.logfile.log(error)
        if reset:
            time.sleep(5)
            machine.reset()

    def loop(self):
        # disable blue heartbeat blink
        pycom.heartbeat(False)
        print("** starting loop... (interval = {} seconds)\n".format(CFG.interval))
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
            if CFG.interval > passed_time:
                pycom.rgbled(0)  # LED off
                time.sleep(CFG.interval - passed_time)


main = Main()
main.loop()
