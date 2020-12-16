import pycom
from network import Server

# disable the FTP Server
server = Server()
server.deinit()

# disable the wifi on boot
pycom.wifi_on_boot(False)