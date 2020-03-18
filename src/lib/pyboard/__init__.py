from .pycoproc import Pycoproc


class Pyboard(Pycoproc):

    def __init__(self):
        super().__init__(i2c=None, sda='P22', scl='P21')
        self.voltage = self.read_battery_voltage

    def get_data(self) -> dict:
        """
        Get data from the sensors
        :return: a dictionary (json) with the data
        """
        raise NotImplementedError


class Pysense(Pyboard):

    def __init__(self):
        """Initialized sensors on Pysense"""
        super().__init__()

        from .LIS2HH12 import LIS2HH12
        from .LTR329ALS01 import LTR329ALS01
        from .SI7006A20 import SI7006A20
        from .MPL3115A2 import MPL3115A2, ALTITUDE, PRESSURE

        self.accelerometer = LIS2HH12(self)
        self.light = LTR329ALS01(self).light
        self.humidity = SI7006A20(self)
        self.barometer = MPL3115A2(self, mode=PRESSURE)
        # self.altimeter = MPL3115A2(self, mode=ALTITUDE)

    def get_data(self) -> dict:
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


class Pytrack(Pyboard):

    def __init__(self):
        """Initialize sensors on Pytrack"""
        super().__init__()

        from .LIS2HH12 import LIS2HH12
        from .L76GNSS import L76GNSS

        self.accelerometer = LIS2HH12(self)
        self.location = L76GNSS(self, timeout=30)

    def get_data(self) -> dict:
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


def get_sensors(type: str) -> Pyboard:
    if type == "pysense":
        return Pysense()
    elif type == "pytrack":
        return Pytrack()
    else:
        raise Exception("Expansion board type {} not supported. Supported types: 'pysense' and 'pytrack'".format(type))


def print_data(data: dict) -> None:
    print("{")
    for key in sorted(data):
        print("  \"{}\": {},".format(key, data[key]))
    print("}\n")
