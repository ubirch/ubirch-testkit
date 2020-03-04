import json
import logging
from machine import SD
import os

logger = logging.getLogger(__name__)


def get_config(filename: str = "config.json") -> dict:
    # load configuration from config.json file
    # the config.json should be placed next to this file
    # {
    #    "sim": <true or false>,
    #    "connection": "<'wifi' or 'nbiot'>",
    #    "networks": {                          # todo default value (None)
    #      "<WIFI SSID>": "<WIFI PASSWORD>"
    #    },
    #    "apn": "<APN for NB IoT connection",   # todo default value (None or TestKit SIM APN)
    #    "type": "<'pysense' or 'pytrack'>",    # todo default value (pysense or Pycoproc)
    #    "password": "<password for the ubirch backend>",
    #    "keyService": "<URL of key registration service>",
    #    "niomon": "<URL of authentication service>",
    #    "data": "<URL of data service>"
    #    "verify": "<URL of verification service>"
    #    "boot": "<URL of bootstrap service>",
    #    "logfile": <true or false>,
    #    "debug": <true or false>,
    #    "interval": <measure interval in seconds>
    # }
    try:
        with open(filename, 'r') as c:
            cfg = json.load(c)
    except OSError:
        raise Exception("missing configuration file: " + filename)

    # set ubirch protocol implementation (SIM or standard ubirch library using ed25519)
    if 'sim' not in cfg:
        cfg['sim'] = False
        # todo this default value makes ensures that users of previous versions don't have to update their config file
        #  but it is not the right value for the TestKit which uses the ubirch SIM

    # if SIM is present, default connection type is NB-IoT, otherwise it is WIFI
    if 'connection' not in cfg:
        cfg['connection'] = "nbiot" if cfg['sim'] else "wifi"

    # look for ubirch backend password. If it is not in standard config file, look for it on SD card
    if 'password' not in cfg:
        # mount SD card (operation throws exception if no SD card present)
        # fixme can't mount twice, so writing UUID in main will fail if not mounted here
        #  os.unmount('/sd') causes AttributeError: 'module' object has no attribute 'unmount'
        api_config_file = '/sd/config.txt'
        try:
            sd = SD()
            os.mount(sd, '/sd')
            # get config from SD card
            print("** looking for API config on SD card ({})".format(api_config_file))
            with open(api_config_file, 'r') as f:
                api_config = json.load(f)
                print("** found API config on SD card: {}".format(api_config))
            sd.deinit()
        except OSError:
            raise Exception("!! missing config. no password found in {} or {}. ".format(filename, api_config_file))

        # add API config to existing config
        cfg.update(api_config)

    # set default URLs for services that are not set in config file
    if 'env' not in cfg:
        cfg['env'] = "prod"

    if 'niomon' not in cfg:
        cfg['niomon'] = "https://niomon.{}.ubirch.com/".format(cfg['env'])
        print("authentication service URL not set in config file. Setting it to default: " + cfg['niomon'])

    # now make sure the env key has the actual environment value that is used in the URL
    cfg['env'] = cfg['niomon'].split(".")[1]

    # and set remaining URLs
    if 'keyService' not in cfg:
        cfg['keyService'] = "https://key.{}.ubirch.com/api/keyService/v1/pubkey/mpack".format(cfg['env'])
        print("key service URL not set in config file. Setting it to default: " + cfg['keyService'])
    if 'data' not in cfg:
        cfg['data'] = "https://data.{}.ubirch.com/v1/msgPack".format(cfg['env'])
        print("data service URL not set in config file. Setting it to default: " + cfg['data'])
    if 'verify' not in cfg:
        cfg['verify'] = "https://verify.{}.ubirch.com/api/upp".format(cfg['env'])
        print("verification service URL not set in config file. Setting it to default: " + cfg['verify'])
    if 'boot' not in cfg:
        cfg['boot'] = "https://api.console.{}.ubirch.com/ubirch-web-ui/api/v1/devices/bootstrap".format(cfg['env'])
        print("bootstrap service URL not set in config file. Setting it to default: " + cfg['boot'])

    # set default values for miscellaneous configurations
    if 'interval' not in cfg:  # the measure interval in seconds
        cfg['interval'] = 60
    if 'debug' not in cfg:  # enable/disable extensive debug output
        cfg['debug'] = False
    if 'logfile' not in cfg:  # enable/disable logging to file
        cfg['logfile'] = False

    # todo not sure about this.
    #  pro: user can take sd card out after first init;
    #  con: user can't change config by writing new config to sd card
    # write everything to config file (ujson does not support json.dump())
    with open(filename, 'w') as f:
        f.write(json.dumps(cfg))

    return cfg
