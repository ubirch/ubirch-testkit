import machine
import os
import pycom
import sys
import time

LED_OFF = 0x000000
LED_WHITE = 0x111111
LED_GREEN = 0x000200
LED_YELLOW = 0x020200
LED_ORANGE = 0x040200
LED_RED = 0x020000
LED_PURPLE = 0x020002
LED_BLUE = 0x000042

LED_TURQUOISE = 0x40E0D0
LED_PINK = 0xFF1493


def set_led(led_color):
    pycom.heartbeat(False)  # disable blue heartbeat blink
    pycom.rgbled(led_color)


def print_to_console(error: str or Exception):
    if isinstance(error, Exception):
        sys.print_exception(error)
    else:
        print(error)


class ErrorHandler:

    def __init__(self, file_logging_enabled: bool = False, max_file_size_kb: int = 10, sd_card: bool = False):
        self.logfile = None
        if file_logging_enabled:
            self.logfile = FileLogger(max_file_size_kb=max_file_size_kb, log_to_sd_card=sd_card)

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

    def __init__(self, max_file_size_kb: int = 10, log_to_sd_card: bool = False):
        # set up error logging to log file
        self.rtc = machine.RTC()
        self.MAX_FILE_SIZE = max_file_size_kb * 1000  # in bytes
        self.logfile = ('/sd/' if log_to_sd_card else '') + 'log.txt'
        with open(self.logfile, 'a') as f:
            self.file_position = f.tell()
        print("++ file logging enabled")
        print("\tfile: \"{}\"".format(self.logfile))
        print("\tcurrent size:     {: 6.2f} KB".format(self.file_position / 1000.0))
        print("\tmaximal size:     {: 6.2f} KB".format(self.MAX_FILE_SIZE / 1000.0))
        print("\tfree flash memory:{: 6d} KB".format(os.getfree('/flash')))
        if log_to_sd_card:
            print("\tfree SD memory:   {: 6d} MB".format(int(os.getfree('/sd') / 1000)))
        print("")

    def log(self, error: str or Exception):
        # stop logging to file once file reached its max size
        if self.file_position >= self.MAX_FILE_SIZE:
            return

        # log error message to file
        with open(self.logfile, 'a') as f:
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
