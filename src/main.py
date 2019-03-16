import pycom
import time
import machine
import math
import _thread
import ubinascii as binascii
import urequests as requests
from uuid import UUID
from wifi import wifi_init

# pycom modules
from SI7006A20 import SI7006A20
from pysense import Pysense

# ubirch specific imports
from ubirch import UbirchProtocol
from ubirch import UBIRCH_PROTOCOL_TYPE_REG, UBIRCH_PROTOCOL_TYPE_BIN

# the settings.py should be place next to this file
# it contains a dict with configurations:
# config = { 'wifi': ['SSID', 'PASSWORD'] }
from settings import config as cfg

pycom.heartbeat(False)
print("** ubirch-protocol example v1.0")

# starting up
wifi_init(cfg["wifi"][0], cfg["wifi"][1])

# set up ubirch protocol
device_uuid = UUID(b'UBIR'+ 2*machine.unique_id())
print("UUID   : "+str(device_uuid))
proto = UbirchProtocol(device_uuid)

# register device identity
cert = proto.get_certificate()
regi = proto.message_signed(device_uuid, UBIRCH_PROTOCOL_TYPE_REG, cert)
r = requests.post("https://key.dev.ubirch.com/api/keyService/v1/pubkey/mpack",
                  headers = {'Content-Type': 'application/octet-stream'},
                  data=regi)
if r.status_code == 200:
    print(str(device_uuid)+": identity registered")
else:
    print(str(device_uuid)+": ERROR: device identity not registered")


def breathe():
    while True:
        v = int((math.exp(math.sin(time.ticks_ms()/2000*math.pi)) - 0.36787944)*108.0)
        pycom.rgbled((v << 16) + (v << 8) + v)

# start the breathing of our RGB led
_thread.start_new_thread(breathe, ())

# our main loop
py = Pysense()
si = SI7006A20(py)
rtc = machine.RTC()
interval = 60
while True:
    # prepare message
    timestamp = rtc.now()
    ts = time.mktime(timestamp) * 1000000 + timestamp[6]
    data = [ts, int(si.humidity()*100), int(si.temperature()*100)]
    msg = proto.message_signed(device_uuid, 0x32, data)
    r = requests.post("https://api.ubirch.dev.ubirch.com/api/avatarService/v1/device/update/mpack",
                      data=msg)
    try:
        response = proto.message_verify(r.content)
        print(response)
        print("response: "+repr(response[4]))
        interval = response[4][b'i']
    except Exception as e:
        print("response: verification failed")
    time.sleep(interval)
