print("*** UBIRCH SIM Testkit TESTING unsolicited messages ***")
import time

# remember wake-up time
start_time = time.time()

import machine

# set watchdog: if execution hangs/takes longer than 'timeout' an automatic reset is triggered
# we need to do this as early as possible in case an import cause a freeze for some reason
wdt = machine.WDT(timeout=5 * 60 * 1000)  # we set it to 5 minutes here and will reconfigure it when we have loaded the configuration
wdt.feed()  # we only feed it once since this code hopefully finishes with deepsleep (=no WDT) before reset_after_ms

from binascii import hexlify, b2a_base64
from config import load_config
from connection import get_connection, NB_IoT
from error_handling import *
from helpers import *
from modem import get_imsi, get_signalquality, LTEunsolQ
from os import listdir, uname
from realtimeclock import *

import ubirch

import sqnsupgrade

# Pycom specifics
from pyboard import get_pyboard

# error color codes
COLOR_INET_FAIL = LED_PURPLE_BRIGHT
COLOR_BACKEND_FAIL = LED_ORANGE_BRIGHT
COLOR_SIM_FAIL = LED_RED_BRIGHT
COLOR_CONFIG_FAIL = LED_YELLOW_BRIGHT
COLOR_MODEM_FAIL = LED_PINK_BRIGHT
COLOR_UNKNOWN_FAIL = LED_WHITE_BRIGHT

#############
#   SETUP   #
#############
# signal beginning of main code
set_led(LED_PINK)

# check reset cause
COMING_FROM_DEEPSLEEP = (machine.reset_cause() == machine.DEEPSLEEP_RESET)

# mount SD card if there is one
print("++ mounting SD")
SD_CARD_MOUNTED = mount_sd()
if SD_CARD_MOUNTED:
    print("\tSD card mounted")
else:
    print("\tno SD card found")

# set up error handling
max_file_size_kb = 10240 if SD_CARD_MOUNTED else 20
error_handler = ErrorHandler(file_logging_enabled=True, max_file_size_kb=max_file_size_kb,
                             sd_card=SD_CARD_MOUNTED)
try:
    # get system information
    print("pycom firmware: ", uname())
    #print("modem firmware: ", sqnsupgrade.info())

    # initialize modem
    lte = LTEunsolQ()

    try:
        # reset modem on any non-normal loop (modem might be in a strange state)
        if not COMING_FROM_DEEPSLEEP:
            print("++ not coming from sleep, resetting modem")
            reset_modem(lte, cereg_level=2, debug_print=True)

        print("++ getting IMSI")
        imsi = get_imsi(lte)
        print("IMSI: " + imsi)
    except Exception as e:
        print("\tERROR setting up modem")
        error_handler.log(e, COLOR_MODEM_FAIL)
        while True:
            machine.idle()

    # write IMSI to SD card
    if not COMING_FROM_DEEPSLEEP and SD_CARD_MOUNTED: store_imsi(imsi)

    set_led(LED_TURQUOISE)

    # load configuration, blocks in case of failure
    print("++ loading config")
    try:
        cfg = load_config(sd_card_mounted=SD_CARD_MOUNTED)

        #lvl_debug = cfg['debug']  # set debug level
        lvl_debug = False
        if lvl_debug: print("\t" + repr(cfg))

        interval = cfg['interval']  # set measurement interval
        sensors = get_pyboard(cfg['board'])  # initialise the sensors on the pyboard
        connection = get_connection(lte, cfg)  # initialize connection object depending on config
        api = ubirch.API(cfg)  # set up API for backend communication
    except Exception as e:
        print("\tERROR loading configuration")
        error_handler.log(e, COLOR_CONFIG_FAIL)
        while True:
            machine.idle()

    #configure watchdog and connection timeouts according to config and reset reason
    if COMING_FROM_DEEPSLEEP:
        #this is a normal boot after sleep
        wdt.init(cfg["watchdog_timeout"]*1000)
        if isinstance(connection, NB_IoT):
            connection.setattachtimeout(cfg["nbiot_attach_timeout"])
            connection.setconnecttimeout(cfg["nbiot_connect_timeout"])
    else:
        #this is a boot after powercycle or error: use extended timeouts
        wdt.init(cfg["watchdog_extended_timeout"]*1000)
        if isinstance(connection, NB_IoT):
            connection.setattachtimeout(cfg["nbiot_extended_attach_timeout"])
            connection.setconnecttimeout(cfg["nbiot_extended_connect_timeout"])

    # get PIN from flash, or bootstrap from backend and then save PIN to flash
    pin_file = imsi + ".bin"
    pin = get_pin_from_flash(pin_file, imsi)
    if pin is None:
        try:
            connection.connect()
        except Exception as e:
            error_handler.log(e, COLOR_INET_FAIL, reset=True)

        try:
            pin = bootstrap(imsi, api)
            with open(pin_file, "wb") as f:
                f.write(pin.encode())
        except Exception as e:
            error_handler.log(e, COLOR_BACKEND_FAIL, reset=True)

    # disconnect from LTE connection before accessing SIM application
    # (this is only necessary if we are connected via LTE)
    if isinstance(connection, NB_IoT):
        print("\tdisconnecting")
        connection.disconnect()

    set_led(LED_ORANGE)

    # initialise ubirch SIM protocol
    print("++ initializing ubirch SIM protocol")
    try:
        sim = ubirch.SimProtocol(lte=lte, at_debug=lvl_debug)
    except Exception as e:
        error_handler.log(e, COLOR_SIM_FAIL, reset=True)

    # unlock SIM
    try:
        sim.sim_auth(pin)
    except Exception as e:
        error_handler.log(e, COLOR_SIM_FAIL)
        # if PIN is invalid, there is nothing we can do -> block
        if isinstance(e, ValueError):
            print("PIN is invalid, can't continue")
            while True:
                wdt.feed()  # avert reset from watchdog
                set_led(COLOR_SIM_FAIL)
                time.sleep(0.5)
                set_led(LED_OFF)
                time.sleep(0.5)
        else:
            machine.reset()

    # get UUID from SIM
    key_name = "ukey"
    uuid = sim.get_uuid(key_name)
    print("UUID: " + str(uuid))

    # send a X.509 Certificate Signing Request for the public key to the ubirch identity service (once)
    csr_file = "csr_{}_{}.der".format(uuid, api.env)
    if csr_file not in os.listdir():
        try:
            connection.connect()
        except Exception as e:
            error_handler.log(e, COLOR_INET_FAIL, reset=True)

        try:
            csr = submit_csr(key_name, cfg["CSR_country"], cfg["CSR_organization"], sim, api)
            with open(csr_file, "wb") as f:
                f.write(csr)
        except Exception as e:
            error_handler.log(e, COLOR_BACKEND_FAIL)

    # if the board does not have a time set, synchronize it
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

        # set start time again with valid time
        start_time = time.time()

    if isinstance(connection, NB_IoT):
        print("\tdisconnecting")
        connection.disconnect()

    ##############
    #   TESING   #
    ##############
    try:
        while True:
            # get signal quality
            sigq = get_signalquality(lte)
            print("signal quality: " + sigq)
            for ii in range(50):
                # generate APDU command traffic
                if len(sim.get_key(key_name)) > 0:
                    print('.', end='')
                time.sleep(0.01)
            print()
            unsolmsg = lte.unsolQ_pop()
            while unsolmsg is not None:
                print("unsolicited msg: ", unsolmsg)
                unsolmsg = lte.unsolQ_pop()
    except Exception as e:
        error_handler.log(e, COLOR_INET_FAIL, reset=False)

except Exception as e:
    error_handler.log(e, COLOR_UNKNOWN_FAIL, reset=True)
