# ubirch TestKit

### Components
- 1NCE SIM Card with SIGNiT application
- Pycom GPy
- Pycom Pysense
- Pycom LTE antenna
- micro SD card
- micro USB cable

### What you need
- micro SD card writer

### Getting started
1. Register at the [ubirch web UI](https://console.prod.ubirch.com) and log in.
 (TODO: bootstrapping currently only deployed on dev stage -> go to https://console.dev.ubirch.com  for now)
1. Go to `Things` and click on `+ ADD NEW DEVICE`. Enter the IMSI of your SIM card to the `ID` field
 and click on `register`. (TODO: not implemented yet)
1. Click on the newly registered "Thing" (your IMSI) and copy the `apiConfig`.
1. Create a file `config.txt` on the SD card and paste the configuration into it. It should look like this:
    ```json
    {
      "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx",
      "keyService": "https://key.prod.ubirch.com/api/keyService/v1/pubkey/mpack",
      "niomon": "https://niomon.prod.ubirch.com/",
      "data": "https://data.prod.ubirch.com/v1/msgPack"
    }
    ```
1. Insert the SD card into the Pysense (TODO: picture of TestKit with arrow where to put SD card),
 make sure the antenna is attached to the Gpy and power up the TestKit with the micro USB cable.
  (TODO: more arrows where to put antenna and USB cable)
 
The LED on the GPy flashes in blue colour during the initialization process.
 If anything goes wrong, the LED will change colour:

| colour | meaning | what to do |
|--------|---------|------------|
| yellow | couldn't get config from SD card | Make sure the SD card is inserted correctly and has a file named `config.txt` with the API config from the ubirch web UI. The content of the file should look like the example in step 4 including the braces (`{` `}`).
| purple | couldn't connect to network (resets automatically) | Try to find a place with better signal or connect to WIFI instead. (see [here](#configuration))
| red | couldn't acquire PIN to unlock SIM from ubirch backend or other backend related issue | Make sure you have registered the correct IMSI at the [ubirch web UI](https://console.prod.ubirch.com) and you copied the `apiConfig` for your IMSI to the `config.txt` file on the DS card.
| green | it's all good. device is measuring, sending data, sealing and sending data certificate to the ubirch backend| see next chapter |
| orange | sending data or data certificate to the ubirch backend failed |  |
| off | sleeping until the next measurement interval (60 seconds) | 

### See the data
TODO

### Verify the hash
TODO

### Configuration
You can configure your device by adding further key-value pairs to the `config.txt`-file on the SD card.
 These are the configuration options:
 ```json
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
```
There are default values for everything except for the `password`-key.

The default connection type is NB-IoT, but if you can not connect to a NB-IoT network, you can change it to WIFI by adding
 ```json
        "connection": "wifi",
        "networks": {
          "<WIFI SSID>": "<WIFI PASSWORD>"
        },
```
to your config file and replacing `<WIFI SSID>` with your SSID and `<WIFI PASSWORD>` with your password.

### Log file
TODO