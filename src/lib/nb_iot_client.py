import logging
import time
from uuid import UUID

from network import LTE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

lte = LTE()


def nb_iot_connect(apn: str):
    lte.attach(band=8, apn=apn)
    i = 0
    while not lte.isattached() and i < 100:
        time.sleep(1.0)
        print("not attached" + str(i))
        i = i + 1
    print("attached: " + str(i))

    lte.connect()       # start a data session and obtain an IP address
    i = 0
    while not lte.isconnected():
        time.sleep(0.5)
        print("not connected" + str(i))
        i = i + 1
    print("connected")


class NbIotClient:

    def __init__(self, uuid: UUID, cfg: dict):
        print("NB IoT Client init")
        nb_iot_connect(cfg["apn"])
