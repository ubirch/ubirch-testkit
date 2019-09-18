import json
from binascii import b2a_base64, a2b_base64
from hashlib import sha256
from time import time
from hmac import HMAC
from urllib.parse import quote_plus, urlencode, quote
from umqtt.simple import MQTTClient


class AzureClient(MQTTClient):

    def __init__(self):

        # load azure configuration
        with open("azure.json") as a:
            azure = json.load(a)
        endpoint = azure['endpoint']
        self.device_id = azure['name']
        key = azure['key']
        policy = azure['policy']

        # configure the URI for authentication (same as HTTP)
        uri = "{hostname}/devices/{device_id}".format(
            hostname=endpoint,
            device_id=self.device_id
        )
        # configure username and password from config
        username = "{hostname}/{device_id}/api-version=2018-06-30".format(
            hostname=endpoint,
            device_id=self.device_id
        )
        password = self.generate_sas_token(uri, key, policy)

        # initialize underlying  MQTT client
        super().__init__(self.device_id, endpoint, user=username, password=password, ssl=True, port=8883)

    def generate_sas_token(self, uri, key, policy_name="iothubowner", expiry=None):
        # uri = quote(uri, safe='').lower()
        encoded_uri = quote(uri, safe='')

        if expiry is None:
            expiry = time() + 3600
        ttl = int(expiry)

        sign_key = '%s\n%d' % (encoded_uri, ttl)
        signature = b2a_base64(HMAC(a2b_base64(key), sign_key.encode('utf-8'), sha256).digest())

        result = 'SharedAccessSignature ' + urlencode({
            'sr': uri,
            'sig': signature[:-1],
            'se': str(ttl),
            'skn': policy_name
        })

        return result

    def send(self, msg):
        topic = "devices/{device_id}/messages/events/".format(device_id=self.device_id)

        super().publish(topic, msg, qos=1)