import machine
import time
import sys

NTP_SERVER_DEFAULT = "134.130.4.17"
SYNC_INTERVAL_DEFAULT = 3600

rtc = machine.RTC()

def enable_time_sync(server=NTP_SERVER_DEFAULT,interval=SYNC_INTERVAL_DEFAULT):
    rtc.ntp_sync(server, interval)

def disable_time_sync():
    rtc.ntp_sync(None)

def wait_for_sync(timeout=60,print_dots=True):    
    i = 0    
    while not rtc.synced():
        if print_dots: sys.stdout.write(".")
        time.sleep(1.0)
        i += 1
        if i > timeout:
            raise Exception("timeout when waiting for time sync")
    return

def board_time():
    return rtc.now()

def board_time_valid():
    return (board_time()[0] >= 2020)