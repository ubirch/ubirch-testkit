import machine
import os
import time
from config import load_config
from connection import get_connection
from error_handling import *
from modem import get_imsi
from network import LTE

# Pycom specifics
from pyboard import init_pyboard

# ubirch client
from ubirch import UbirchClient

try:
    # mount SD card if there is one
    sd = machine.SD()
    os.mount(sd, '/sd')
    SD_CARD_MOUNTED = True
except OSError:
    SD_CARD_MOUNTED = False


class Main:
    """ ubirch SIM TestKit """

    def __init__(self):
        lte = LTE()

        imsi = get_imsi(lte)
        print("IMSI: {}\n".format(imsi))

        # load configuration
        try:
            self.cfg = load_config(sd_card_mounted=SD_CARD_MOUNTED)
        except Exception as e:
            set_led(LED_YELLOW)
            print_to_console(e)
            while True:
                machine.idle()

        print("** loaded configuration")
        if self.cfg['debug']: print(repr(self.cfg))

        # set up error handling
        self.error_handler = ErrorHandler(file_logging_enabled=self.cfg['logfile'], sd_card=SD_CARD_MOUNTED)

        # connect to network
        try:
            self.connection = get_connection(lte, self.cfg)
            self.connection.connect()
        except Exception as e:
            self.error_handler.log(e, LED_PURPLE, reset=True)

        # initialise ubirch client
        try:
            self.ubirch_client = UbirchClient(self.cfg, lte, imsi)
        except Exception as e:
            self.error_handler.log(e, LED_RED)
            # if pin is invalid, there is nothing we can do -> block
            if isinstance(e, ValueError):
                print("invalid PIN, can't continue")
                while True:
                    set_led(LED_RED)
                    time.sleep(0.5)
                    set_led(LED_OFF)
                    time.sleep(0.5)
            else:
                machine.reset()

        # initialise the sensors
        self.sensors = init_pyboard(self.cfg['board'])

        # taken from LIS2HH12.py
        #   ARG => threshold
        #   3 => max 8G; resolution: 125   micro G
        #   2 => max 4G; resolution: 62.5  micro G
        #   0 => max 2G; resolution: 31.25 micro G
        self.sensors.accelerometer.set_full_scale(3)

        # taken from LIS2HH12.py
        #   ARG => duration
        #   0 => POWER DOWN
        #   1 => 10  Hz; resolution: 800 milli seconds; max duration: 204000 ms
        #   2 => 50  Hz; resolution: 160 milli seconds; max duration: 40800  ms
        #   3 => 100 Hz; resolution: 80  milli seconds; max duration: 20400  ms
        #   4 => 200 Hz; resolution: 40  milli seconds; max duration: 10200  ms
        #   5 => 400 Hz; resolution: 20  milli seconds; max duration: 5100   ms
        #   6 => 500 Hz; resolution: 10  milli seconds; max duration: 2550   ms
        self.sensors.accelerometer.set_odr(4)

        # enable activity interrupt
        self.sensors.accelerometer.enable_activity_interrupt(self.cfg['interrupt_threshold_mg'],
                                                             self.cfg['threshold_duration_ms'], self.interrup_cb)

        set_led(LED_OFF)

    def loop(self):
        while True:
            machine.idle()

    def interrup_cb(self, pin):
        set_led(LED_BLUE)

        # disable interrupt
        self.sensors.accelerometer.enable_activity_interrupt(self.cfg['interrupt_threshold_mg'],
                                                             self.cfg['threshold_duration_ms'], None)

        # make sure device is still connected or reconnect
        try:
            self.connection.connect()
        except Exception as e:
            self.error_handler.log(e, LED_PURPLE, reset=True)

        # send data to ubirch data service and certificate to ubirch auth service
        try:
            self.ubirch_client.send({
                "threshold_mg": self.cfg['interrupt_threshold_mg'],
                "duration_ms": self.cfg['threshold_duration_ms']
            }, callback=set_led, args=LED_GREEN)
        except Exception as e:
            self.error_handler.log(e, LED_ORANGE)

        # re-enable interrupt
        self.sensors.accelerometer.enable_activity_interrupt(self.cfg['interrupt_threshold_mg'],
                                                             self.cfg['threshold_duration_ms'], self.interrup_cb)

        set_led(LED_OFF)


main = Main()
main.loop()
