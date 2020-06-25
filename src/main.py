print("*** UBIRCH SIM Testkit ***")
print("++ importing:")
print("\tmachine")
import machine

print("\ttime")
import time

# set watchdog: if execution hangs/takes longer than 'timeout' an automatic reset is triggered
# we need to do this as early as possible in case an import cause a freeze for some reason
print("++ enabling watchdog")
wdt = machine.WDT(timeout=5 * 60 * 1000)  # set it
wdt.feed()  # we only feed it once since this code hopefully finishes with deepsleep (=no WDT) before reset_after_ms

# remember wake-up time
print("++ saving boot time")
start_time = time.time()

print("++ continue with importing:")
print("\tOS")
import os

print("\tconfig")
from config import load_config

print("\tconnection")
from connection import get_connection

print("\terror handling")
from error_handling import *

print("\tmodem")
from modem import get_imsi, reset_modem

print("\trealtimeclock")
from realtimeclock import *

print("\tnetwork")
from network import LTE

print("\tubirch")
import ubirch

print("\thelpers")
from helpers import *

# print("\tubinascii")
# from ubinascii import b2a_base64, a2b_base64, hexlify, unhexlify

print("\tpyboard")
# Pycom specifics
from pyboard import init_pyboard


#### Function Definitions ###
def mount_sd():
    try:
        sd = machine.SD()
        os.mount(sd, '/sd')
        return True
    except OSError:
        return False


def store_imsi(imsi):
    # save imsi to file on SD, SD needs to be mounted
    imsi_file = "imsi.txt"
    if imsi_file not in os.listdir('/sd'):
        print("\twriting IMSI to SD")
        with open('/sd/' + imsi_file, 'w') as f:
            f.write(imsi)


def get_pin_from_flash(pin_file) -> str or None:
    if pin_file in os.listdir():
        print("\tloading PIN for " + imsi)
        with open(pin_file, "rb") as f:
            return f.readline().decode()
    else:
        return None


def send_backend_data(sim: ubirch.SimProtocol, lte: LTE, api_function, uuid, data) -> (int, bytes):
    MAX_MODEM_RESETS = 1  # number of retries with modem reset before giving up
    MAX_RECONNECTS = 1  # number of retries with reconnect before trying a modem reset

    for reset_attempts in range(MAX_MODEM_RESETS + 1):
        # check if this is a retry for reset_attempts
        if reset_attempts > 0:
            print("\tretrying with modem reset")
            sim.deinit()
            reset_modem(lte)  # TODO: should probably be connection.reset_hardware()
            connection.connect()

        # try to send multiple times (with reconnect)
        try:
            for send_attempts in range(MAX_RECONNECTS + 1):
                # check if this is a retry for send_attempts
                if send_attempts > 0:
                    print("\tretrying with disconnect/reconnect")
                    connection.disconnect()
                    connection.connect()
                try:
                    print("\tsending...")
                    return api_function(uuid, data)
                except Exception as e:
                    # TODO: log/print exception?
                    print("\tsending failed: {}".format(e))
                    # (continues to top of send_attempts loop)
            else:
                # all send attempts used up
                raise Exception("all send attempts failed")
        except Exception as e:
            print(repr(e))
            # (continues to top of reset_attempts loop)
    else:
        # all modem resets used up
        raise Exception("could not establish connection to backend")


### Main Code ###
# error color codes
COLOR_INET_FAIL = LED_PURPLE
COLOR_BACKEND_FAIL = LED_ORANGE
COLOR_SIM_FAIL = LED_RED
COLOR_CONFIG_FAIL = LED_RED

# signal beginning of main code
set_led(LED_GREEN)

# intialize globals
lte = LTE()

# check reset cause
COMING_FROM_DEEPSLEEP = (machine.reset_cause() == machine.DEEPSLEEP_RESET)

# do modem reset on any non-normal loop (modem might be in a strange state)
if not COMING_FROM_DEEPSLEEP:
    print("++ not coming from sleep, resetting modem")
    reset_modem(lte)

# mount SD card if there is one
print("++ trying to mount SD")
SD_CARD_MOUNTED = mount_sd()

print("++ getting IMSI")
imsi = get_imsi(lte)

if not COMING_FROM_DEEPSLEEP and SD_CARD_MOUNTED: store_imsi(imsi)

# load configuration, blocks in case of failure
print("++ trying to load config")
try:
    cfg = load_config(sd_card_mounted=SD_CARD_MOUNTED)
    print("\tOK")
except Exception as e:
    print("\tError")
    set_led(COLOR_CONFIG_FAIL)
    print_to_console(e)
    while True:
        machine.idle()

if cfg['debug']: print("\t" + repr(cfg))

# create connection object depending on config
connection = get_connection(lte, cfg)

# set measurement interval
interval = cfg['interval']

# set up error handling
error_handler = ErrorHandler(file_logging_enabled=cfg['logfile'], sd_card=SD_CARD_MOUNTED)

# set up API for backend communication
api = ubirch.API(cfg)
key_name = "ukey"

# get pin from flash, or bootstrap from backend and save
pin_file = imsi + ".bin"
pin = get_pin_from_flash(pin_file)
if pin is None:
    try:
        connection.connect()
        pin = bootstrap(imsi, api)
        connection.disconnect()
        with open(pin_file, "wb") as f:
            f.write(pin.encode())
    except Exception as e:
        error_handler.log(e, COLOR_BACKEND_FAIL, reset=True)

# initialise ubirch SIM protocol
print("++ initializing ubirch SIM protocol")
try:
    sim = ubirch.SimProtocol(lte=lte, at_debug=cfg['debug'])
except Exception as e:
    error_handler.log(e, COLOR_SIM_FAIL, reset=True)

# unlock SIM
try:
    sim.sim_auth(pin)
except:
    # if pin is invalid, there is nothing we can do -> block
    while True:
        wdt.feed()  # avert reset from watchdog
        print("PIN is invalid, can't continue")
        set_led(COLOR_SIM_FAIL)
        time.sleep(0.5)
        set_led(0)
        time.sleep(0.5)

# get UUID from SIM
uuid = sim.get_uuid(key_name)
print("\tUUID: " + str(uuid))

# # send a X.509 Certificate Signing Request for the public key to the ubirch identity service
csr_file = "csr_{}_{}.der".format(uuid, api.env)
if csr_file not in os.listdir():
    try:
        connection.connect()
        csr = submit_csr(key_name, sim, api)
        connection.disconnect()
        with open(csr_file, "wb") as f:
            f.write(csr)
    except Exception as e:
        error_handler.log(e, COLOR_BACKEND_FAIL, reset=True)

# check if the board has a time set, if not synchronize it
print("++ checking board time\n\ttime is: ", board_time())
if not board_time_valid():  # time can't be correct -> connect to sync time
    print("\ttime invalid, syncing")
    # connect to network, set time, disconnect afterwards to speed up SIM communication
    try:
        connection.connect()
        enable_time_sync()
        print("\twaiting for time sync")
        wait_for_sync(print_dots=False)
    except Exception as e:
        error_handler.log(e, COLOR_INET_FAIL, reset=True)
    print("\tdisconnecting")
    connection.disconnect()

# initialise the sensors
print("++ intializing sensors")
sensors = init_pyboard(cfg['board'])

# get data from sensors
print("++ getting measurements")
data = sensors.get_data()
# print_data(data)

## pack data and create UPP ##

# pack data message containing measurements, device UUID and timestamp to ensure unique hash
print("++ packing data")
message = pack_data_json(uuid, data)
# print("\tdata message [json]: {}\n".format(message.decode()))

# seal the data message (data message will be hashed and inserted into UPP as payload by SIM card)
print("++ creating UPP")
upp = sim.message_chained(key_name, message, hash_before_sign=True)
# print("\tUPP [msgpack]: {} (base64: {})\n".format(hexlify(upp).decode(),
#                                                    b2a_base64(upp).decode().rstrip('\n')))
# retrieve data message hash from generated UPP for verification
# message_hash = get_upp_payload(upp)
# print("\tdata message hash: {}".format(b2a_base64(message_hash).decode()))

print("++ checking/establishing connection")
try:
    connection.connect()
    enable_time_sync()
except Exception as e:
    error_handler.log(e, COLOR_INET_FAIL, reset=True)

# send data to ubirch data service and certificate to ubirch auth service
# TODO: add retrying to send/handling of already created UPP in case of final failure

try:
    # send data message to data service, with reconnects/modem resets if necessary
    print("++ sending data")
    status_code, content = send_backend_data(sim, lte, api.send_data, uuid, message)

    # communication worked in general, now check server response
    if status_code != 200:
        raise Exception("backend (data) returned error: ({}) {}".format(status_code, str(content)))

    # send UPP to the ubirch authentication service to be anchored to the blockchain
    print("++ sending UPP")
    status_code, content = send_backend_data(sim, lte, api.send_upp, uuid, upp)

    # communication worked in general, now check server response
    if status_code != 200:
        raise Exception("backend (UPP) returned error:: ({}) {}".format(status_code, str(content)))

except Exception as e:
    error_handler.log(e, COLOR_BACKEND_FAIL)

print("++ waiting for time sync")
try:
    wait_for_sync(print_dots=True, timeout=10)
except Exception as e:
    print("\nWarning: Could not sync time before timeout")

# prepare hardware for sleep (needed for low current draw and
# freeing of ressources for after the reset, as the modem stays on)
print("++ preparing hardware for sleep")
print("\tclose connection")
connection.disconnect()
print("\tdeinit SIM")
sim.deinit()
# not detaching causes smaller/no re-attach time on next reset but but 
# somewhat higher sleep current needs to be balanced based on your specific interval
print("\tdeinit LTE")
lte.deinit(detach=False)

# go to deepsleep
sleep_time = interval - int(time.time() - start_time)
if sleep_time < 0:
    sleep_time = 0
print(">> going to deepsleep for {} seconds".format(sleep_time))
set_led(0)  # LED off
machine.deepsleep(1000 * sleep_time)  # sleep, execution will resume from main.py entry point
