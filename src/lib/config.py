import os
import ujson as json

NIOMON_SERVICE = "https://niomon.{}.ubirch.com"
DATA_SERVICE = "https://data.{}.ubirch.com/v1"
BOOTSTRAP_SERVICE = "https://api.console.{}.ubirch.com/ubirch-web-ui/api/v1/devices/bootstrap"
IDENTITY_SERVICE = "https://identity.{}.ubirch.com/api/certs/v1/csr/register"


def load_config(sd_card_mounted: bool = False) -> dict:
    """
    Load available configurations. First set default configuration (see "default_config.json"),
    then overwrite defaults with configuration from user config file ("config.json")
    the config file should be placed in the same directory than this file
    {
        "connection": "<'wifi' or 'nbiot'>",
        "apn": "<APN for NB IoT connection",
        "band": <LTE frequency band (integer) or 'null' to scan all bands>,
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
        "CSR_country": "DE",
        "CSR_organization": "ubirch GmbH",
        "interval": <measure interval in seconds>,
        "debug": <true or false>
    }
    :param user_config: the user config file
    :return: a dict with the available configurations
    """

    # load default config
    default_config = "default_config.json"
    with open(default_config, 'r') as c:
        cfg = json.load(c)

    # overwrite default config with user config if there is one
    user_config = "config.json"
    if user_config in os.listdir():
        with open(user_config, 'r') as c:
            user_cfg = json.load(c)
            cfg.update(user_cfg)

    # overwrite existing config with config from sd card if there is one
    sd_config = 'config.txt'
    if sd_card_mounted and sd_config in os.listdir('/sd'):
        with open('/sd/' + sd_config, 'r') as c:
            api_config = json.load(c)
            cfg.update(api_config)

    # ensure that the ubirch backend auth token is set
    if cfg['password'] is None:
        raise Exception("missing auth token")

    # set default values for unset service URLs
    if 'niomon' not in cfg:
        cfg['niomon'] = NIOMON_SERVICE.format(cfg['env'])

    # now make sure the env key has the actual environment value that is used in the URL
    cfg['env'] = cfg['niomon'].split(".")[1]
    if cfg['env'] not in ["dev", "demo", "prod"]:
        raise Exception("invalid ubirch backend environment \"{}\"".format(cfg['env']))

    # and set remaining URLs
    if 'data' not in cfg:
        cfg['data'] = DATA_SERVICE.format(cfg['env'])
    else:
        cfg['data'] = cfg['data'].rstrip("/msgPack")

    if 'bootstrap' not in cfg:
        cfg['bootstrap'] = BOOTSTRAP_SERVICE.format(cfg['env'])

    if 'identity' not in cfg:
        cfg['identity'] = IDENTITY_SERVICE.format(cfg['env'])

    return cfg
