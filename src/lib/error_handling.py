import machine
import os
import pycom
import sys

import time

LED_GREEN = 0x002200
LED_YELLOW = 0x444400
LED_ORANGE = 0x442200
LED_RED = 0x7f0000
LED_PURPLE = 0x220022


def set_led(led_color):
    pycom.heartbeat(False)
    pycom.rgbled(led_color)


def print_to_console(error):
    if isinstance(error, Exception):
        sys.print_exception(error)
    else:
        print(error)


class ErrorHandler:

    def __init__(self, file_logging_enabled: bool = False, sd_card_mounted: bool = False):
        self.file_logging_enabled = file_logging_enabled
        if self.file_logging_enabled:
            self.logfile = FileLogger(sd_card_mounted)

    def report(self, error: str or Exception, led_color: int, reset: bool = False):
        set_led(led_color)
        print_to_console(error)
        self.log_to_file(error)
        if reset:
            time.sleep(5)
            machine.reset()

    def log_to_file(self, error):
        if self.file_logging_enabled:
            self.logfile.log(error)


class FileLogger:
    MAX_FILE_SIZE = 10000  # in bytes

    def __init__(self, sd_card_mounted: bool = False):
        # set up error logging to log file
        self.rtc = machine.RTC()
        self.path = '/sd/' if sd_card_mounted else ''
        self.logfile_name = 'log.txt'
        with open(self.path + self.logfile_name, 'a') as f:
            self.file_position = f.tell()
        print("** file logging enabled\n"
              "-- name: {}\n"
              "-- size: {:.1f} kb (free flash memory: {:d} kb)\n".format(
            self.path + self.logfile_name, self.file_position / 1000.0, os.getfree('/flash')))

    def log(self, error: str or Exception):
        with open(self.path + self.logfile_name, 'a') as f:
            # start overwriting oldest logs once file reached its max size
            # known issue:
            #  once file reached its max size, file position will always be set to beginning after device reset
            if self.file_position > self.MAX_FILE_SIZE:
                self.file_position = 0
            # set file to recent position
            f.seek(self.file_position, 0)

            # log error message and traceback if error is an exception
            t = self.rtc.now()
            f.write('{:04d}.{:02d}.{:02d} {:02d}:{:02d}:{:02d} {}\n'.format(t[0], t[1], t[2], t[3], t[4], t[5], error))

            # remember current file position
            self.file_position = f.tell()
