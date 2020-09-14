import machine
import os
import time
from config import load_config
from error_handling import *

# Pycom specifics
from pyboard import init_pyboard


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

        # initialise the sensors
        self.sensors = init_pyboard(self.cfg['board'])

        # taken from LIS2HH12.py
        #   ARG => threshold
        #   3 => max 8G; resolution: 125   micro G
        #   2 => max 4G; resolution: 62.5  micro G
        #   0 => max 2G; resolution: 31.25 micro G
        self.sensors.accelerometer.set_full_scale(0)

        # taken from LIS2HH12.py
        #   ARG => duration
        #   0 => POWER DOWN
        #   1 => 10  Hz; resolution: 800 milli seconds; max duration: 204000 ms
        #   2 => 50  Hz; resolution: 160 milli seconds; max duration: 40800  ms
        #   3 => 100 Hz; resolution: 80  milli seconds; max duration: 20400  ms
        #   4 => 200 Hz; resolution: 40  milli seconds; max duration: 10200  ms
        #   5 => 400 Hz; resolution: 20  milli seconds; max duration: 5100   ms
        #   6 => 500 Hz; resolution: 10  milli seconds; max duration: 2550   ms
        self.sensors.accelerometer.set_odr(6)

        # enable activity interrupt
        self.sensors.accelerometer.enable_activity_interrupt(self.cfg['interrupt_threshold_mg'],
                                                             self.cfg['threshold_duration_ms'], self.interrup_cb)

        set_led(LED_OFF)

    def loop(self):
        while True:
            machine.idle()

    def interrup_cb(self, pin):
        # disable interrupt
        self.sensors.accelerometer.enable_activity_interrupt(self.cfg['interrupt_threshold_mg'],
                                                             self.cfg['threshold_duration_ms'], None)

        for _ in range(2):
            set_led(LED_RED)
            time.sleep(0.4)
            set_led(LED_BLUE)
            time.sleep(0.4)

        set_led(LED_OFF)

        # re-enable interrupt
        self.sensors.accelerometer.enable_activity_interrupt(self.cfg['interrupt_threshold_mg'],
                                                             self.cfg['threshold_duration_ms'], self.interrup_cb)



main = Main()
main.loop()
