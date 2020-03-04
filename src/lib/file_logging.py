from machine import RTC
import os
import sys

rtc = RTC()

MAX_FILE_SIZE = 10000  # in bytes


class Logfile:

    def __init__(self):
        # set up error logging to log file
        self.logfile_name = 'log.txt'
        with open(self.logfile_name, 'a') as f:
            self.file_position = f.tell()
        print(
            "** file logging enabled\n"
            "-- log file name: {}\n"
            "-- size: {:.1f} kb\n"
            "-- free flash memory: {:d} kb\n".format(
                self.logfile_name, self.file_position / 1000.0, os.getfree('/flash')))

    def log(self, error: str or Exception):
        with open(self.logfile_name, 'a') as f:
            # start overwriting oldest logs once file reached its max size
            # known issue: once file reached its max size,
            # file position will always be set to beginning after device reset
            if self.file_position > MAX_FILE_SIZE:
                self.file_position = 0
            # set file to recent position
            f.seek(self.file_position, 0)

            # log error message and traceback if error is an exception
            t = rtc.now()
            f.write('({:04d}.{:02d}.{:02d} {:02d}:{:02d}:{:02d}) '.format(t[0], t[1], t[2], t[3], t[4], t[5]))
            if isinstance(error, Exception):
                sys.print_exception(error, f)
            else:
                f.write(error + "\n")

            # remember current file position
            self.file_position = f.tell()
