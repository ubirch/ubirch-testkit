import machine
import os
import ujson as json
from uuid import UUID

NIOMON_SERVICE = "https://niomon.{}.ubirch.com/"
KEY_SERVICE = "https://key.{}.ubirch.com/api/keyService/v1/pubkey/mpack"
DATA_SERVICE = "https://data.{}.ubirch.com/v1/msgPack"
VERIFICATION_SERVICE = "https://verify.{}.ubirch.com/api/upp"
BOOTSTRAP_SERVICE = "https://api.console.{}.ubirch.com/ubirch-web-ui/api/v1/devices/bootstrap"

# mount SD card if there is one
try:
    sd = machine.SD()
    os.mount(sd, '/sd')
    SD_CARD_MOUNTED = True
except OSError:
    SD_CARD_MOUNTED = False


def get_config(user_config: str = "config.json") -> dict:
    """
    Load available configurations. First set default configuration (see "default_config.json"),
    then overwrite defaults with configuration from user config file ("config.json")
    the config.json should be placed next to this file
    {
        "sim": <true or false>,
        "connection": "<'wifi' or 'nbiot'>",
        "apn": "<APN for NB IoT connection",
        "networks": {
          "<WIFI SSID>": "<WIFI PASSWORD>"
        },
        "board": "<'pysense' or 'pytrack'>",
        "password": "<password for the ubirch backend>",
        "keyService": "<URL of key registration service>",
        "niomon": "<URL of authentication service>",
        "data": "<URL of data service>",
        "verify": "<URL of verification service>",
        "bootstrap": "<URL of bootstrap service>",
        "logfile": <true or false>,
        "debug": <true or false>,
        "interval": <measure interval in seconds>
    }
    :param user_config: the user config file
    :return: a dict with the available configurations
    """

    # load default config
    default_config = "default_config.json"
    with open(default_config, 'r') as c:
        cfg = json.load(c)

    # overwrite default config with user config there is one
    if user_config in os.listdir('.'):
        with open(user_config, 'r') as c:
            user_cfg = json.load(c)
            cfg.update(user_cfg)

    # generate UUID if no SIM is used (otherwise UUID shall be retrieved from SIM)
    if not cfg['sim']:
        cfg['uuid'] = UUID(b'UBIR' + 2 * machine.unique_id())
        print("** UUID   : " + str(cfg['uuid']) + "\n")

        if SD_CARD_MOUNTED:
            # write UUID to file on SD card if file doesn't already exist
            uuid_file = "uuid.txt"
            if uuid_file not in os.listdir('/sd'):
                with open('/sd/' + uuid_file, 'w') as f:
                    f.write(str(cfg['uuid']))

    # if ubirch backend password is missing, look for it on SD card
    if cfg['password'] is None:
        api_config_file = 'config.txt'
        # get config from SD card
        if SD_CARD_MOUNTED and api_config_file in os.listdir('/sd'):
            with open('/sd/' + api_config_file, 'r') as f:
                api_config = json.load(f)
                # update existing config with API config from SD card
                cfg.update(api_config)
        else:
            raise Exception("!! no password set")

    # ensure that all necessary service URLs have been set and set default values if not
    if 'niomon' not in cfg:
        cfg['niomon'] = NIOMON_SERVICE.format(cfg['env'])

    # now make sure the env key has the actual environment value that is used in the URL
    cfg['env'] = cfg['niomon'].split(".")[1]

    # and set remaining URLs
    if 'keyService' not in cfg:
        cfg['keyService'] = KEY_SERVICE.format(cfg['env'])
    if 'data' not in cfg:
        cfg['data'] = DATA_SERVICE.format(cfg['env'])
    if 'verify' not in cfg:
        cfg['verify'] = VERIFICATION_SERVICE.format(cfg['env'])
    if 'bootstrap' not in cfg:
        cfg['bootstrap'] = BOOTSTRAP_SERVICE.format(cfg['env'])

    return cfg
