# Copyright (c) 2018 ubirch GmbH.
#
# @author Matthias L. Jugel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import logging
import os
import time
from uuid import UUID

import paho.mqtt.client as mqtt

class C8yBootstrapClient:
    def __init__(self, client: mqtt.Client, password: str):
        self.client = client
        self.client.username_pw_set("management/devicebootstrap", password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.loop_start()

        self.client.tls_set()
        self.client.connect("ubirch.cumulocity.com", 8883)

        self.connected = False
        while not self.connected:
            time.sleep(10)

        self.authorized = False
        while not self.authorized:
            self.client.publish("s/ucr")
            time.sleep(10)

        client.disconnect()
        client.loop_stop()

    def on_connect(self, client, userdata, flags, rc):
        self.client.subscribe("s/dcr")
        self.connected = True

    def on_message(self, client, userdata, message):
        print("on_message(): {}".format(message.payload.decode()))
        if message.payload.startswith(b'70'):
            print("received authorization".format(message.payload))
            self.authorization = message.payload
            self.authorized = True

    def get_authorization(self):
        return self.authorization

class C8yMQTTClient:
    def __init__(self, client: mqtt.Client, tenant: str, auth: str):
        (username, password) = auth.split(":")

        self.receivedMessages = []

        self.tenant = tenant
        self.client = client
        self.client.enable_print
        self.auth = auth
        self.client.username_pw_set("{}/{}".format(tenant, username), password)
        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_publish = self.on_publish
        self.client.loop_start()

        try: self.client.tls_set()
        except Exception as e:
            print(e)

        self.connected = False
        self.client.connect("{}.cumulocity.com".format(tenant), 8883)
        while not self.connected:
            time.sleep(1)

    def __del__(self):
        self.client.loop_stop()

    def on_connect(self, client, userdata, flags, rc):
        self.connected = True
        print("on_connect()")
        if print() == logging.DEBUG:
            print("subscribe: {}".format(self.client.subscribe("s/e")))
        print("subscribe: {}".format(self.client.subscribe("s/ds")))

    def on_message(self, userdata, message):
        print("on_message(): {}".format(message.payload))

    def on_subscribe(self, client, userdata, mid, qos):
        print("on_subscribe(): {}".format(mid))

    def on_publish(self, client, userdata, mid):
        print("on_publish(): ACK {}".format(mid))
        self.receivedMessages.append(mid)

    def publish(self, topic, message, wait_for_ack = False):
        mid = self.client.publish(topic, message, 0)[1]
        if (wait_for_ack):
            while mid not in self.receivedMessages:
                time.sleep(0.25)
            self.receivedMessages.remove(mid)


def client(uuid: UUID):
    mqtt_client = mqtt.Client(client_id=str(uuid))
    auth_file = str(uuid) + ".c8y"
    if auth_file in os.listdir("/flash"):
        with open(auth_file) as f:
            auth = f.read().encode()
    else:
        bootstrap_client = C8yBootstrapClient(mqtt_client, auth)
        auth = bootstrap_client.get_authorization()
        with open("/flash/" + auth_file) as f:
            f.write(auth)

    (tenant, username, password) = auth[3:].decode().split(",")
    return C8yClient(mqtt_client, tenant, username+":"+password)
