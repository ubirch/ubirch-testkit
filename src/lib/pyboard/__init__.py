from .pycoproc import Pycoproc

from .SI7006A20 import SI7006A20
from .MPL3115A2 import MPL3115A2,ALTITUDE,PRESSURE
from .LTR329ALS01 import LTR329ALS01
from .LIS2HH12 import LIS2HH12


class Pysense(Pycoproc):
    def __init__(self):
        """Initialized sensors on Pysense"""
        super().__init__(i2c=None, sda='P22', scl='P21')
        self.barometer = MPL3115A2(self, mode=PRESSURE)
        self.altimeter = MPL3115A2(self, mode=ALTITUDE)
        self.humidity = SI7006A20(self)
        self.light = LTR329ALS01(self).light
        self.accelerometer = LIS2HH12(self)
        self.voltage = self.read_battery_voltage


class Pytrack(Pycoproc):
    def __init__(self):
        """Initialize sensors on Pytrack"""
        super().__init__(i2c=None, sda='P22', scl='P21')

        self.accelerometer = LIS2HH12(self)
        self.voltage = self.read_battery_voltage
