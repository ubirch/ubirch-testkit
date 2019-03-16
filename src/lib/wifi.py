import machine
import time
from network import WLAN

def wifi_init(ssid, pwd):
    wlan = WLAN(mode=WLAN.STA)
    nets = wlan.scan()
    print("-- searching for wifi networks...")
    for net in nets:
        if net.ssid == ssid:
            print('-- wifi network '+net.ssid+' found, connecting ...')
            wlan.connect(ssid, auth=(net.sec, pwd), timeout=5000)
            while not wlan.isconnected():
                machine.idle() # save power while waiting
            print('-- wifi network connected')
            print('-- IP address: ' + str(wlan.ifconfig()))
            rtc = machine.RTC()
            rtc.ntp_sync('pool.ntp.org', 3600)
            while not rtc.synced():
                time.sleep(1)
            print('-- current time: '+str(rtc.now()))
            break
