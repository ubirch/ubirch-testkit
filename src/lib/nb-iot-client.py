import logging
import socket
import ssl
from uuid import UUID

import uselect as select
from network import LTE
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

lte= LTE()

def nb_iot_connect():
    lte.attach(band=8, apn="iot.telekom.net")
    i=0
    while not lte.isattached() and i < 100:
        time.sleep(1.0)
        print("not attached" + str(i) + " band " + str(x[j]))
        i=i+1
    print("attached: " + str(i))

    lte.connect()       # start a data session and obtain an IP address
    i=0
    while not lte.isconnected():
        time.sleep(0.5)
        print("not connected" + str(i))
        i=i+1
    print("conected")



class NbIotClient:

    def __init__(self, uuid: UUID, cfg: dict):
        nb_iot_connect()

        a = socket.getaddrinfo('www.postman-echo.com', 443)[0][-1]
        s= socket.socket()
        s.setblocking(False)
        s = ssl.wrap_socket(s)
        try:
            s.connect(a)
        except OSError as e:
            if str(e) == '119': # For non-Blocking sockets 119 is EINPROGRESS
                print("In Progress")
            else:
                raise e
        poller = select.poll()
        poller.register(s, select.POLLOUT | select.POLLIN)
        while True:
            res = poller.poll(1000)
            if res:
                if res[0][1] & select.POLLOUT:
                    print("Doing Handshake")
                    s.do_handshake()
                    print("Handshake Done")
                    s.send(b"GET / HTTP/1.0\r\n\r\n")
                    poller.modify(s,select.POLLIN)
                    continue
                if res[0][1] & select.POLLIN:
                    print(s.recv(4092))
                    break
            break
