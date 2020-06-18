import machine
import os
import time
from config import load_config
from connection import init_connection
from error_handling import *
from modem import get_imsi, _send_at_cmd
from network import LTE

# Pycom specifics
from pyboard import init_pyboard, print_data

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
    set_led(LED_GREEN)
    return time.time()


def sleep_until_next_interval(start_time, interval):
    # wait for next interval
    sleep_time = interval - int(time.time() - start_time)
    if sleep_time > 0:
        print(">> sleep for {} seconds".format(sleep_time))
        set_led(0)  # LED off
        machine.idle()
        time.sleep(sleep_time)


class Main:
    """ ubirch SIM TestKit """

    def __init__(self):
        lte = LTE()

        print("Resetting modem...")
        lte.reset()
        lte.init()
        print("Done")

        _send_at_cmd(lte,"AT+CFUN=1")
        time.sleep(5)
        _send_at_cmd(lte,"AT+CFUN?")

        imsi = get_imsi(lte)

        imsi_file = "imsi.txt"
        if SD_CARD_MOUNTED and imsi_file not in os.listdir('/sd'):
            with open('/sd/' + imsi_file, 'w') as f:
                f.write(imsi)

        # load configuration
        try:
            cfg = load_config(sd_card_mounted=SD_CARD_MOUNTED)
        except Exception as e:
            set_led(LED_YELLOW)
            print_to_console(e)
            while True:
                machine.idle()

        print("** loaded configuration")
        if cfg['debug']: print(repr(cfg))

        # set up error handling
        self.error_handler = ErrorHandler(file_logging_enabled=cfg['logfile'], sd_card=SD_CARD_MOUNTED)

        # connect to network
        try:
            self.connection = init_connection(lte, cfg)
        except Exception as e:
            self.error_handler.log(e, LED_PURPLE, reset=True)

        # initialise ubirch client
        try:
            self.ubirch_client = UbirchClient(cfg, lte, imsi)
        except Exception as e:
            self.error_handler.log(e, LED_RED, reset=True)

        # initialise the sensors
        self.sensors = init_pyboard(cfg['board'])

        # set measurement interval
        self.interval = cfg['interval']

    def loop(self):
        print("\n** starting loop (interval = {} seconds)\n".format(self.interval))
        while True:
            start_time = wake_up()

            # get data
            print("** getting measurements:")
            data = self.sensors.get_data()
            print_data(data)

            # make sure device is still connected or reconnect
            if not self.connection.is_connected() and not self.connection.connect():
                self.error_handler.log("!! unable to reconnect to network", LED_PURPLE, reset=True)

            # send data to ubirch data service and certificate to ubirch auth service
            try:
                self.ubirch_client.send(data)
            except Exception as e:
                self.error_handler.log(e, LED_ORANGE)

            print("** done\n")
            sleep_until_next_interval(start_time, self.interval)


main = Main()
main.loop()
