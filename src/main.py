print("*** UBIRCH SIM Testkit ***")
import time
import machine

# set watchdog: if execution hangs/takes longer than 'timeout' an automatic reset is triggered
# we need to do this as early as possible in case an import cause a freeze for some reason
wdt = machine.WDT(timeout=5 * 60 * 1000)
wdt.feed()

from binascii import hexlify, b2a_base64
from config import load_config
from connection import get_connection, NB_IoT
from error_handling import *
from helpers import *
from modem import get_imsi
from network import LTE
from os import listdir
from realtimeclock import *

import ubirch

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
    # initialize modem
    lte = LTE()

    try:
        # reset modem on any non-normal loop (modem might be in a strange state)
        if not COMING_FROM_DEEPSLEEP:
            print("++ not coming from sleep, resetting modem")
            reset_modem(lte)

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

        lvl_debug = cfg['debug']  # set debug level
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

    # configure connection timeouts according to config
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

    if isinstance(connection, NB_IoT):
        print("\tdisconnecting")
        connection.disconnect()

    # reconfigure watchdog
    wdt.init(interval * 1000)

    while True:
        wdt.feed()
        start_time = time.time()

        ############
        #   DATA   #
        ############
        set_led(LED_BLUE)

        # get data from sensors
        print("++ getting measurements")
        data = sensors.get_temp_and_hum()

        # pack data message containing measurements as well as device UUID and timestamp to ensure unique hash
        message = pack_data_json(uuid, data)
        print("\tdata message [json]: {}\n".format(message.decode()))

        # seal the data message (data message will be hashed and inserted into UPP as payload by SIM card)
        try:
            print("++ creating UPP")
            upp = sim.message_chained(key_name, message, hash_before_sign=True)
            print("\tUPP: {}\n".format(hexlify(upp).decode()))
            # print data message hash from generated UPP (useful for manual verification)
            message_hash = get_upp_payload(upp)
            print("\tdata message hash: {}".format(b2a_base64(message_hash).decode()))
        except Exception as e:
            error_handler.log(e, COLOR_SIM_FAIL, reset=True)

        ###############
        #   SENDING   #
        ###############
        set_led(LED_GREEN)

        print("++ checking/establishing connection")
        try:
            connection.connect()
            enable_time_sync()
        except Exception as e:
            error_handler.log(e, COLOR_INET_FAIL, reset=True)

        # send data to ubirch data service and UPP to ubirch auth service
        # TODO: add retrying to send/handling of already created UPP in case of final failure

        try:
            # send data message to data service, with reconnects/modem resets if necessary
            print("++ sending data")
            try:
                status_code, content = send_backend_data(sim, lte, connection, api.send_data, uuid, message)
            except Exception as e:
                error_handler.log(e, COLOR_MODEM_FAIL, reset=True)

            # communication worked in general, now check server response
            if not 200 <= status_code < 300:
                raise Exception("backend (data) returned error: ({}) {}".format(status_code, str(content)))

            # send UPP to the ubirch authentication service to be anchored to the blockchain
            print("++ sending UPP")
            try:
                status_code, content = send_backend_data(sim, lte, connection, api.send_upp, uuid, upp)
            except Exception as e:
                error_handler.log(e, COLOR_MODEM_FAIL, reset=True)

            # communication worked in general, now check server response
            if not 200 <= status_code < 300:
                raise Exception("backend (UPP) returned error: ({}) {}".format(status_code, str(content)))

        except Exception as e:
            error_handler.log(e, COLOR_BACKEND_FAIL)

        print("++ waiting for time sync")
        try:
            wait_for_sync(print_dots=True, timeout=10)
            print("\ttime synced")
        except Exception as e:
            error_handler.log("WARNING: Could not sync time before timeout: {}".format(repr(e)), COLOR_INET_FAIL)

        ###################
        #   GO TO SLEEP   #
        ###################
        if isinstance(connection, NB_IoT):
            print("\tdisconnecting")
            connection.disconnect()

        wdt.feed()

        # wait for next interval
        sleep_time = interval - int(time.time() - start_time)
        if sleep_time > 0:
            print(">> sleep for {} seconds".format(sleep_time))
            set_led(LED_OFF)
            machine.idle()
            time.sleep(sleep_time)

except Exception as e:
    error_handler.log(e, COLOR_UNKNOWN_FAIL, reset=True)
