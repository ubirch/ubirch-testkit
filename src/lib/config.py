import json
import logging

logger = logging.getLogger(__name__)


def get_config(filename: str = "config.json") -> dict:
    # load configuration from config.json file
    # the config.json should be placed next to this file
    # {
    #    "connection": "<'wifi' or 'nbiot'>",
    #    "networks": {
    #      "<WIFI SSID>": "<WIFI PASSWORD>"
    #    },
    #    "apn": "<APN for NB IoT connection",
    #    "type": "<'pysense' or 'pytrack'>",
    #    "password": "<password for the ubirch backend>",
    #    "keyService": "<URL of key registration service>",
    #    "niomon": "<URL of authentication service>",
    #    "data": "<URL of data service>"
    #    "verify": "<URL of verification service>"
    # }
    try:
        with open(filename, 'r') as c:
            cfg = json.load(c)
    except OSError:
        raise Exception("missing configuration file: " + filename)

    # throw exception if password for ubirch backend is missing
    if 'password' not in cfg:
        raise Exception("password missing in configuration file: " + filename)

    # set default URLs for services that are not set in config file
    if 'env' not in cfg:
        cfg['env'] = "prod"
    if 'keyService' not in cfg:
        cfg['keyService'] = "https://key.{}.ubirch.com/api/keyService/v1/pubkey/mpack".format(cfg['env'])
        logger.debug("key service URL not set in config file. Setting it to default: " + cfg['keyService'])

    # now make sure the env key has the actual environment value that is used in the URL
    cfg['env'] = cfg['keyService'].split(".")[1]

    if 'niomon' not in cfg:
        cfg['niomon'] = "https://niomon.{}.ubirch.com/".format(cfg['env'])
        logger.debug("authentication service URL not set in config file. Setting it to default: " + cfg['niomon'])
    if 'data' not in cfg:
        cfg['data'] = "https://data.{}.ubirch.com/v1/msgPack".format(cfg['env'])
        logger.debug("data service URL not set in config file. Setting it to default: " + cfg['data'])
    if 'verify' not in cfg:
        cfg['verify'] = "https://verify.{}.ubirch.com/api/upp".format(cfg['env'])
        logger.debug("verification service URL not set in config file. Setting it to default: " + cfg['verify'])

    # set default values for various configurations
    if 'interval' not in cfg:  # the measure interval in seconds
        cfg['interval'] = 60
    if 'debug' not in cfg:  # enable/disable extensive debug output
        cfg['debug'] = False
    if 'logfile' not in cfg:  # enable/disable logging to file
        cfg['logfile'] = False

    return cfg
