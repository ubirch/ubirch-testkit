import machine
import os
import pycom
import sys
import time

LED_GREEN = 0x002200
LED_YELLOW = 0x222200
LED_ORANGE = 0x442200
LED_RED = 0x7f0000
LED_PURPLE = 0x220022
LED_BLUE = 0x0055AA
LED_OFF = 0x0


def set_led(led_color):
    pycom.heartbeat(False)  # disable blue heartbeat blink
    pycom.rgbled(led_color)


def print_to_console(error: str or Exception):
    if isinstance(error, Exception):
        sys.print_exception(error)
    else:
        print(error)


class ErrorHandler:

    def __init__(self, file_logging_enabled: bool = False, sd_card: bool = False):
        self.logfile = None
        if file_logging_enabled:
            self.logfile = FileLogger(sd_card)

    def log(self, error: str or Exception, led_color: int, reset: bool = False):
        set_led(led_color)
        print_to_console(error)
        if self.logfile is not None:
            self.logfile.log(error)
        machine.idle()
        time.sleep(3)
        if reset:
            print(">> Resetting device...")
            time.sleep(1)
            machine.reset()


class FileLogger:
    MAX_FILE_SIZE = 20000  # in bytes

    def __init__(self, sd_card_mounted: bool = False):
        # set up error logging to log file
        self.rtc = machine.RTC()
        self.logfile = ('/sd/' if sd_card_mounted else '') + 'log.txt'
        with open(self.logfile, 'a') as f:
            self.file_position = f.tell()
        print(">> file logging enabled")
        print("-- file: \"{}\"".format(self.logfile))
        print("-- current size:     {: 6.2f} KB".format(self.file_position / 1000.0))
        print("-- maximal size:     {: 6.2f} KB".format(self.MAX_FILE_SIZE / 1000.0))
        print("-- free flash memory:{: 6d} KB".format(os.getfree('/flash')))
        if sd_card_mounted:
            print("-- free SD memory:   {: 6d} MB".format(int(os.getfree('/sd') / 1000)))
        print("")

    def log(self, error: str or Exception):
        with open(self.logfile, 'a') as f:
            # start overwriting oldest logs once file reached its max size
            # known issue:
            #  once file reached its max size, file position will always be set to beginning after device reset
            if self.file_position > self.MAX_FILE_SIZE:
                self.file_position = 0
            # set file to recent position
            f.seek(self.file_position, 0)

            # log error message and traceback if error is an exception
            t = self.rtc.now()
            f.write('({:04d}.{:02d}.{:02d} {:02d}:{:02d}:{:02d}) '.format(t[0], t[1], t[2], t[3], t[4], t[5]))
            if isinstance(error, Exception):
                sys.print_exception(error, f)
            else:
                f.write(error + "\n")

            # remember current file position
            self.file_position = f.tell()
