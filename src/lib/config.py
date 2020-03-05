import json
import os


class Config:

    def __init__(self, filename: str = "config.json"):
        # load configuration from config.json file
        # the config.json should be placed next to this file
        # {
        #    "sim": <true or false>,
        #    "connection": "<'wifi' or 'nbiot'>",
        #    "networks": {
        #      "<WIFI SSID>": "<WIFI PASSWORD>"
        #    },
        #    "apn": "<APN for NB IoT connection",
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

        self.filename = filename

        cfg = {}
        if filename in os.listdir('.'):
            with open(self.filename, 'r') as c:
                cfg = json.load(c)

        # set ubirch protocol implementation (ubirch SIM or ubirch library using ed25519)
        # todo this default value makes ensures that users of previous versions don't have to update their config file
        #  but it is not the right value for the TestKit which uses the ubirch SIM
        self.sim = cfg.get('sim', False)

        # if SIM is present, default connection type is NB-IoT, otherwise it is WIFI
        self.connection = cfg.get('connection', "nbiot" if self.sim else "wifi")
        self.networks = cfg.get('networks', None)
        self.apn = cfg.get('apn', None)

        self.set_api_config(cfg)

        # set default values for remaining configurations
        self.interval = cfg.get('interval', 60)  # the measure interval in seconds
        self.debug = cfg.get('debug', False)  # enable/disable extensive debug output
        self.logfile = cfg.get('logfile', False)  # enable/disable logging to file

    def set_api_config(self, cfg: dict):
        # get password for ubirch backend, defaults to None
        self.password = cfg.get('password', None)
        # get service URLs from config file or set default URLs for those that are not set in config file
        self.env = cfg.get('env', "prod")
        self.niomon = cfg.get('niomon', "https://niomon.{}.ubirch.com/".format(self.env))
        # now make sure env has the actual environment value that is used in the URL before setting set remaining URLs
        self.env = self.niomon.split(".")[1]
        self.keyService = cfg.get('keyService',
                                  "https://key.{}.ubirch.com/api/keyService/v1/pubkey/mpack".format(self.env))
        self.data = cfg.get('data', "https://data.{}.ubirch.com/v1/msgPack".format(self.env))
        self.verify = cfg.get('verify', "https://verify.{}.ubirch.com/api/upp".format(self.env))
        self.boot = cfg.get('boot',
                            "https://api.console.{}.ubirch.com/ubirch-web-ui/api/v1/devices/bootstrap".format(self.env))
