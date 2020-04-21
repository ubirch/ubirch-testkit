import os
import ujson as json

NIOMON_SERVICE = "https://niomon.{}.ubirch.com/"
KEY_SERVICE = "https://key.{}.ubirch.com/api/keyService/v1/pubkey/mpack"
DATA_SERVICE = "https://data.{}.ubirch.com/v1/msgPack"
VERIFICATION_SERVICE = "https://verify.{}.ubirch.com/api/upp"
BOOTSTRAP_SERVICE = "https://api.console.{}.ubirch.com/ubirch-web-ui/api/v1/devices/bootstrap"


def load_config(user_config: str = "config.json", sd_card_mounted: bool = False) -> dict:
    """
    Load available configurations. First set default configuration (see "default_config.json"),
    then overwrite defaults with configuration from user config file ("config.json")
    the config file should be placed in the same directory than this file
    {
        "connection": "<'wifi' or 'nbiot'>",
        "apn": "<APN for NB IoT connection",
        "networks": {
          "<WIFI SSID>": "<WIFI PASSWORD>"
        },
        "board": "<'pysense' or 'pytrack'>",
        "password": "<auth token for the ubirch backend>",
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

    # if ubirch backend auth token is not set, look for it on SD card
    if cfg['password'] is None:
        api_config_file = 'config.txt'
        if not sd_card_mounted or api_config_file not in os.listdir('/sd'):
            raise Exception("missing auth token")

        # get config from SD card
        with open('/sd/' + api_config_file, 'r') as f:
            api_config = json.load(f)

        # update existing config with API config from SD card
        cfg.update(api_config)

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
