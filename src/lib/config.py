import json
import os


def get_config() -> dict:  # todo make cfg class and have cfg.members instead of dict
    # load configuration from config.json file
    # the config.json should be placed next to this file
    # {
    #    "sim": <true or false>,
    #    "connection": "<'wifi' or 'nbiot'>",
    #    "networks": {                          # todo default value (None)
    #      "<WIFI SSID>": "<WIFI PASSWORD>"
    #    },
    #    "apn": "<APN for NB IoT connection",   # todo default value (None or TestKit SIM APN)
    #    "type": "<'pysense' or 'pytrack'>",    # todo default value (pysense or Pycoproc or figure it out on runtime)
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

    filename = "config.json"

    # todo take this out once there are default values for everything
    if filename not in os.listdir('.'):
        raise FileNotFoundError("missing configuration file: " + filename)

    with open(filename, 'r') as c:
        cfg = json.load(c)

    cfg["filename"] = filename

    # set ubirch protocol implementation (SIM or standard ubirch library using ed25519)
    if 'sim' not in cfg:
        cfg['sim'] = False
        # todo this default value makes ensures that users of previous versions don't have to update their config file
        #  but it is not the right value for the TestKit which uses the ubirch SIM

    # if SIM is present, default connection type is NB-IoT, otherwise it is WIFI
    if 'connection' not in cfg:
        cfg['connection'] = "nbiot" if cfg['sim'] else "wifi"

    # set default URLs for services that are not set in config file
    if 'env' not in cfg:
        cfg['env'] = "prod"

    if 'niomon' not in cfg:
        cfg['niomon'] = "https://niomon.{}.ubirch.com/".format(cfg['env'])

    # now make sure the env key has the actual environment value that is used in the URL
    cfg['env'] = cfg['niomon'].split(".")[1]

    # and set remaining URLs
    if 'keyService' not in cfg:
        cfg['keyService'] = "https://key.{}.ubirch.com/api/keyService/v1/pubkey/mpack".format(cfg['env'])
    if 'data' not in cfg:
        cfg['data'] = "https://data.{}.ubirch.com/v1/msgPack".format(cfg['env'])
    if 'verify' not in cfg:
        cfg['verify'] = "https://verify.{}.ubirch.com/api/upp".format(cfg['env'])
    if 'boot' not in cfg:
        cfg['boot'] = "https://api.console.{}.ubirch.com/ubirch-web-ui/api/v1/devices/bootstrap".format(cfg['env'])

    # set default values for miscellaneous configurations
    if 'interval' not in cfg:  # the measure interval in seconds
        cfg['interval'] = 60
    if 'debug' not in cfg:  # enable/disable extensive debug output
        cfg['debug'] = False
    if 'logfile' not in cfg:  # enable/disable logging to file
        cfg['logfile'] = False

    return cfg
