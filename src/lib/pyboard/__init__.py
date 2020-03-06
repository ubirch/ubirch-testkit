from .L76GNSS import L76GNSS
from .LIS2HH12 import LIS2HH12
from .LTR329ALS01 import LTR329ALS01
from .MPL3115A2 import MPL3115A2, ALTITUDE, PRESSURE
from .SI7006A20 import SI7006A20
from .pycoproc import Pycoproc


class Pyboard:

    def __init__(self):
        try:
            py = Pycoproc()
            v = py.read_hw_version()
            if v == 2:
                self.sensor = Pysense()
            elif v == 3:
                self.sensor = Pytrack()
            else:
                self.sensor = py  # fixme dont know what to do here
        except OSError:
            # raise Exception("Expansion board type not supported. Supported types: Pysense and Pytrack")
            self.sensor = Pysense()  # fixme this is a quick hack because older version of expansion board throw OSError

    def get_data(self) -> dict:
        """
        Get data from the sensors
        :return: a dictionary (json) with the data
        """
        data = {
            "V": self.sensor.voltage()
        }

        if isinstance(self.sensor, Pysense) or isinstance(self.sensor, Pytrack):
            accel = self.sensor.accelerometer.acceleration()
            roll = self.sensor.accelerometer.roll()
            pitch = self.sensor.accelerometer.pitch()

            data.update({
                "AccX": accel[0],
                "AccY": accel[1],
                "AccZ": accel[2],
                "AccRoll": roll,
                "AccPitch": pitch
            })

        if isinstance(self.sensor, Pysense):
            data.update({
                "T": self.sensor.barometer.temperature(),
                "P": self.sensor.barometer.pressure(),
                # "Alt": self.sensor.altimeter.altitude(),
                "H": self.sensor.humidity.humidity(),
                "L_blue": self.sensor.light()[0],
                "L_red": self.sensor.light()[1]
            })

        if isinstance(self.sensor, Pytrack):
            data.update({
                "GPS_long": self.sensor.location.coordinates()[0],
                "GPS_lat": self.sensor.location.coordinates()[1]
            })

        return data


class Pysense(Pycoproc):

    def __init__(self):
        """Initialized sensors on Pysense"""
        super().__init__(i2c=None, sda='P22', scl='P21')
        self.accelerometer = LIS2HH12(self)
        self.light = LTR329ALS01(self).light
        self.humidity = SI7006A20(self)
        self.barometer = MPL3115A2(self, mode=PRESSURE)
        self.altimeter = MPL3115A2(self, mode=ALTITUDE)
        self.voltage = self.read_battery_voltage

    def get_data(self) -> dict:
        """
        Get data from the sensors
        :return: a dictionary (json) with the data
        """
        return {
            "V": self.voltage(),
            "AccX": self.accelerometer.acceleration()[0],
            "AccY": self.accelerometer.acceleration()[1],
            "AccZ": self.accelerometer.acceleration()[2],
            "AccRoll": self.accelerometer.roll(),
            "AccPitch": self.accelerometer.pitch(),
            "T": self.barometer.temperature(),
            "P": self.barometer.pressure(),
            # "Alt": self.altimeter.altitude(),
            "H": self.humidity.humidity(),
            "L_blue": self.light()[0],
            "L_red": self.light()[1]
        }


class Pytrack(Pycoproc):

    def __init__(self):
        """Initialize sensors on Pytrack"""
        super().__init__(i2c=None, sda='P22', scl='P21')

        self.accelerometer = LIS2HH12(self)
        self.location = L76GNSS(self, timeout=30)
        self.voltage = self.read_battery_voltage

    def get_data(self) -> dict:
        """
        Get data from the sensors
        :return: a dictionary (json) with the data
        """
        return {
            "V": self.voltage(),
            "AccX": self.accelerometer.acceleration()[0],
            "AccY": self.accelerometer.acceleration()[1],
            "AccZ": self.accelerometer.acceleration()[2],
            "AccRoll": self.accelerometer.roll(),
            "AccPitch": self.accelerometer.pitch(),
            "GPS_long": self.location.coordinates()[0],
            "GPS_lat": self.location.coordinates()[1]
        }
