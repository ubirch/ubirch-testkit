from .pycoproc import Pycoproc


class Pyboard(Pycoproc):

    def __init__(self):
        super().__init__(i2c=None, sda='P22', scl='P21')

        from .LIS2HH12 import LIS2HH12

        self.accelerometer = LIS2HH12(self)
        self.voltage = self.read_battery_voltage

    def get_data(self) -> dict:
        """
        Get data from the sensors
        :return: a dictionary (json) with the data
        """
        return {
            "AccX": self.accelerometer.acceleration()[0],
            "AccY": self.accelerometer.acceleration()[1],
            "AccZ": self.accelerometer.acceleration()[2],
            "AccRoll": self.accelerometer.roll(),
            "AccPitch": self.accelerometer.pitch(),
            "V": self.voltage()
        }


class Pysense(Pyboard):

    def __init__(self):
        """Initialized sensors on Pysense"""
        super().__init__()

        from .LTR329ALS01 import LTR329ALS01
        from .MPL3115A2 import MPL3115A2, ALTITUDE, PRESSURE
        from .SI7006A20 import SI7006A20

        self.light = LTR329ALS01(self).light
        # self.altimeter = MPL3115A2(self, mode=ALTITUDE)
        self.barometer = MPL3115A2(self, mode=PRESSURE)
        self.humidity = SI7006A20(self)

    def get_data(self) -> dict:
        data = super().get_data()
        data.update({
            "L_blue": self.light()[0],
            "L_red": self.light()[1],
            # "Alt": self.altimeter.altitude(),
            "T": self.barometer.temperature(),
            "P": self.barometer.pressure(),
            "H": self.humidity.humidity()
        })
        return data

    def get_temp_and_hum(self) -> dict:
        """
        Get temperature and humidity measurements
        :return: a dictionary (json) with the data
        """
        return {
            "T": self.barometer.temperature(),
            "H": self.humidity.humidity()
        }


class Pytrack(Pyboard):

    def __init__(self):
        """Initialize sensors on Pytrack"""
        super().__init__()

        from .L76GNSS import L76GNSS

        self.location = L76GNSS(self, timeout=30)

    def get_data(self) -> dict:
        data = super().get_data()
        data.update({
            "GPS_long": self.location.coordinates()[0],
            "GPS_lat": self.location.coordinates()[1]
        })
        return data

class Sht31(Pyboard):

    def __init__(self):
        """Initialized sensors on Pysense"""
        # super().__init__()
        from .adafruit_sht31d import SHT31D
        from machine import I2C

        # Create library object using our Bus I2C port
        i2c = I2C(0, I2C.MASTER, baudrate=100000)
        sensor = SHT31D(i2c)

        self.sensor = sensor

    def get_data(self) -> dict:
        data = {
            "AccX": 0.0,
            "AccY": 0.0,
            "AccZ": 0.0,
            "AccRoll": 0.0,
            "AccPitch": 0.0,
            "V": 0.0
        }
        data.update({
            "T": self.sensor.temperature,
            "H": self.sensor.relative_humidity
        })
        return data

    def get_temp_and_hum(self) -> dict:
        """
        Get temperature and humidity measurements
        :return: a dictionary (json) with the data
        """
        return {
            "T": self.sensor.temperature,
            "H": self.sensor.relative_humidity
        }


def get_pyboard(type: str) -> Pyboard:
    if type == "pysense":
        return Pysense()
    elif type == "pytrack":
        return Pytrack()
    elif type == "sht31":
        return Sht31()
    else:
        raise Exception("Expansion board type {} not supported. Supported types: 'pysense' and 'pytrack'".format(type))


def print_data(data: dict) -> None:
    print("{")
    for key in sorted(data):
        print("  \"{}\": {},".format(key, data[key]))
    print("}\n")
