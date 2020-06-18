import machine
import os
import time
from config import load_config
from connection import init_connection
from error_handling import *
from modem import get_imsi, _send_at_cmd
from network import LTE

# Pycom specifics
from pyboard import init_pyboard, print_data

# ubirch client
from ubirch import UbirchClient

def wake_up():
    set_led(LED_GREEN)
    return time.time()

#begin of main code

#remember wake-up time
start_time = wake_up()

#check reset cause
COMING_FROM_DEEPSLEEP = (machine.reset_cause() == machine.DEEPSLEEP_RESET)

# mount SD card if there is one
try:
    sd = machine.SD()
    os.mount(sd, '/sd')
    SD_CARD_MOUNTED = True
except OSError:
    SD_CARD_MOUNTED = False

#intialization, 
lte = LTE()

if not COMING_FROM_DEEPSLEEP:
    #if we are not coming from deepsleep, modem might be in a strange state (errors/poweron) -> reset
    print("Resetting modem...")
    lte.reset()
    lte.init()
    print("Done")
    _send_at_cmd(lte,"AT+CFUN?")
    _send_at_cmd(lte,"AT+CFUN=1")
    time.sleep(5)
    _send_at_cmd(lte,"AT+CFUN?")

imsi = get_imsi(lte)

if not COMING_FROM_DEEPSLEEP:
    #if not in normal loop operation: save imsi to file
    imsi_file = "imsi.txt"
    if SD_CARD_MOUNTED and imsi_file not in os.listdir('/sd'):
        with open('/sd/' + imsi_file, 'w') as f:
            f.write(imsi)

# load configuration
try:
    cfg = load_config(sd_card_mounted=SD_CARD_MOUNTED)
except Exception as e:
    set_led(LED_YELLOW)
    print_to_console(e)
    while True:
        machine.idle()

print("** loaded configuration")
if cfg['debug']: print(repr(cfg))

# set measurement interval
interval = cfg['interval']

# set up error handling
error_handler = ErrorHandler(file_logging_enabled=cfg['logfile'], sd_card=SD_CARD_MOUNTED)

# connect to network
try:
    connection = init_connection(lte, cfg)
except Exception as e:
    error_handler.log(e, LED_PURPLE, reset=True)

# initialise ubirch client
try:
    ubirch_client = UbirchClient(cfg, lte, imsi)
except Exception as e:
    error_handler.log(e, LED_RED, reset=True)

# initialise the sensors
sensors = init_pyboard(cfg['board'])

# get data
print("** getting measurements:")
data = sensors.get_data()
print_data(data)

# make sure device is still connected or reconnect
if not connection.is_connected() and not connection.connect():
    error_handler.log("!! unable to reconnect to network", LED_PURPLE, reset=True)

# send data to ubirch data service and certificate to ubirch auth service
try:
    ubirch_client.send(data)
except Exception as e:
    error_handler.log(e, LED_ORANGE)

print("** done\n")

#prepare hardware for sleep
print("** preparing hardware for sleep\n")
connection.disconnect()
ubirch_client.sim.deinit()
#TODO: prepare LTE for sleep here

#go to deepsleep
sleep_time = interval - int(time.time() - start_time)
if sleep_time < 0:
    sleep_time = 0
print(">> going to deepsleep for {} seconds".format(sleep_time))
set_led(0)  # LED off
machine.deepsleep(1000*sleep_time)#sleep, execution will resume from main.py entry point




