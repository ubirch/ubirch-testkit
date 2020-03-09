# boot.py -- run on boot-up
import binascii

import pycom

from file_logging import LED_YELLOW
import json
import machine
import os
from config import Config
from uuid import UUID

# mount SD card if there is one
try:
    sd = machine.SD()
    os.mount(sd, '/sd')
    SD_CARD_MOUNTED = True
except OSError:
    SD_CARD_MOUNTED = False

print("\n** MAC    : " + binascii.hexlify(machine.unique_id(), ':').decode() + "\n")

# load configuration from file
CFG = Config()

# generate UUID if no SIM is used (otherwise UUID shall be retrieved from SIM)
PYCOM_UUID = None
if not CFG.sim:
    PYCOM_UUID = UUID(b'UBIR' + 2 * machine.unique_id())
    print("** UUID   : " + str(PYCOM_UUID) + "\n")

    if SD_CARD_MOUNTED:
        # write UUID to file on SD card if file doesn't already exist
        uuid_file = "uuid.txt"
        if uuid_file not in os.listdir('/sd'):
            with open('/sd/' + uuid_file, 'w') as f:
                f.write(str(PYCOM_UUID))

# check if ubirch backend password is already known. If unknown, look for it on SD card.
if CFG.password is None:
    api_config_file = 'config.txt'
    # get config from SD card
    if SD_CARD_MOUNTED and api_config_file in os.listdir('/sd'):
        with open('/sd/' + api_config_file, 'r') as f:
            api_config = json.load(f)  # todo what if password still not in config?
    else:
        pycom.heartbeat(False)
        pycom.rgbled(LED_YELLOW)
        print("!! missing password")  # todo document what yellow LED means for user
        while True:
            machine.idle()

    # add API config from SD card to existing config
    CFG.set_api_config(api_config)
    # print("** configuration:\n{}\n".format(CFG)) todo print config
