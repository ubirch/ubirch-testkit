import math
import time
import pycom
import _thread


class Breathe:

    def __init__(self) -> None:
        self.__running = False

    def breathe(self):
        while self.__running:
            v = int((math.exp(math.sin(time.ticks_ms()/2000*math.pi)) - 0.36787944)*108.0)
            pycom.rgbled((v << 16) + (v << 8) + v)

    def start(self):
        if self.__running:
            return

        self.__running = True
        # start the breathing of our RGB led
        _thread.start_new_thread(self.breathe, ())

    def stop(self):
        self.__running = False
