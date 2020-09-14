import os
import ujson as json

NIOMON_SERVICE = "https://niomon.{}.ubirch.com"
DATA_SERVICE = "https://data.{}.ubirch.com/v1"
BOOTSTRAP_SERVICE = "https://api.console.{}.ubirch.com/ubirch-web-ui/api/v1/devices/bootstrap"
IDENTITY_SERVICE = "https://identity.{}.ubirch.com/api/certs/v1/csr/register"


def load_config(sd_card_mounted: bool = False) -> dict:
    """
    Load "default_config.json",
    :return: a dict with the configurations
    """

    # load default config
    default_config = "default_config.json"
    with open(default_config, 'r') as c:
        cfg = json.load(c)

    return cfg
