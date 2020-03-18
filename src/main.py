import machine
import os
import time
from config import get_config
from connection import get_connection, NB_IoT
from error_handling import ErrorHandler, set_led, print_to_console, LED_GREEN, LED_YELLOW, LED_ORANGE, LED_RED, \
    LED_PURPLE

# Pycom specifics
import pycom
from pyboard import get_sensors, print_data

# ubirch client
from ubirch import UbirchClient

try:
    # mount SD card if there is one
    sd = machine.SD()
    os.mount(sd, '/sd')
    SD_CARD_MOUNTED = True
except OSError:
    SD_CARD_MOUNTED = False


def wake_up():
    # disable blue heartbeat blink
    pycom.heartbeat(False)
    pycom.rgbled(LED_GREEN)
    return time.time()


def sleep_until_next_interval(start_time, interval):
    passed_time = time.time() - start_time
    if interval > passed_time:
        print("\n** going to sleep...\n")
        pycom.rgbled(0)  # LED off
        time.sleep(interval - passed_time)


class Main:
    """ ubirch SIM TestKit """

    def __init__(self):

        # load configuration
        try:
            cfg = get_config(sd_card_mounted=SD_CARD_MOUNTED)
        except Exception as e:
            set_led(LED_YELLOW)
            print_to_console(e)
            while True:
                machine.idle()

        print("** configuration:\n{}\n".format(cfg))

        # set up error handling
        self.error_handler = ErrorHandler(file_logging_enabled=cfg['logfile'], sd_card_mounted=SD_CARD_MOUNTED)

        # connect to network
        try:
            self.connection = get_connection(cfg)
        except OSError as e:
            self.error_handler.report(repr(e) + " Resetting device...", LED_PURPLE, reset=True)

        # initialise ubirch client
        try:
            self.ubirch_client = UbirchClient(cfg, lte=self.connection.lte)
        except Exception as e:
            self.error_handler.report(repr(e) + " Resetting device...", LED_RED, reset=True)

        # initialise the sensors
        self.sensors = get_sensors(cfg['board'])

        # set measurement interval
        self.interval = cfg['interval']

    def loop(self):
        print("** starting loop. interval = {} seconds\n".format(self.interval))
        while True:
            start_time = wake_up()

            # get data
            print("** getting measurements:")
            data = self.sensors.get_data()
            print_data(data)

            # make sure device is still connected or reconnect
            if not self.connection.is_connected() and not self.connection.connect():
                self.error_handler.report("!! unable to connect to network. Resetting device...", LED_PURPLE,
                                          reset=True)

            # send data to ubirch data service and certificate to ubirch auth service
            try:
                self.ubirch_client.send(data)
            except Exception as e:
                self.error_handler.report(e, LED_ORANGE)
                if isinstance(e, OSError):
                    machine.reset()

            # LTE stops working after a while, so we disconnect after sending
            # and reconnect again in the next interval to make sure it still works
            if isinstance(self.connection, NB_IoT):
                self.connection.disconnect()

            sleep_until_next_interval(start_time, self.interval)


main = Main()
try:  # todo
    main.loop()
except Exception as e:
    main.error_handler.report(e, LED_RED, reset=True)
