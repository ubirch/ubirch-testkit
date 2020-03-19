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
1. Register your device at the [ubirch web UI](https://console.prod.ubirch.com):  (TODO: bootstrapping currently only deployed on dev stage -> go to https://console.dev.ubirch.com for now)
    * Once logged in, go to **Things** (in the menu on the left) and click on `+ ADD NEW DEVICE`.  (TODO: not implemented yet)
    * Enter the IMSI of your SIM card to the **ID** field. You can also add a description for your device, if you want.
    * Click on `register`.
    
1. Configure your device:
    * Your IMSI should now show up under **Your Things**. Click on it and copy the `apiConfig`.
    * Create a file `config.txt` on the SD card and paste the configuration into it. It should look like this:
    ```json
        {
            "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx",
            "keyService": "https://key.prod.ubirch.com/api/keyService/v1/pubkey/mpack",
            "niomon": "https://niomon.prod.ubirch.com/",
            "data": "https://data.prod.ubirch.com/v1/msgPack"
        }
    ```
    * Insert the SD card into the Pysense. (TODO: picture of TestKit with arrow where to put SD card)
1. Make sure the antenna is attached to the Gpy and power up the TestKit with the micro USB cable. (TODO: more arrows where to put antenna and USB cable)

**That's it!**

### How it works
After power up, the TestKit will load the configuration from the SD card, connect to the NB-IoT network,
 perform a bootstrap with the **ubirch bootstrap service** to acquire the PIN for the SIM card and then register its public key at the
 **ubirch key service**.
 
Once the initialisation is done, the device will take measurements every minute and send a data message to the **ubirch data service**.
 The data message contains the device UUID, a timestamp and a map with the sensor data:
 ```json
    {
        "AccPitch": "<accelerator Pitch in [deg]>",
        "AccRoll": "<accelerator Roll in [deg]>",
        "AccX": "<acceleration on x-axis in [G]>",
        "AccY": "<acceleration on y-axis in [G]>",
        "AccZ": "<acceleration on z-axis in [G]>",
        "H": "<relative humidity in [%RH]>",
        "L_blue": "<ambient light levels (violet-blue wavelength) in [lux]>",
        "L_red": "<ambient light levels (red wavelength) in [lux]>",
        "P": "<atmospheric pressure in [Pa]>",
        "T": "<external temperature in [°C]>",
        "V": "<supply voltage in [V]>"
    }
 ```
In the next step, the device generates a **Ubirch Protocol Package** (*"UPP"*) with the unique hash of the serialised data,
 UUID and timestamp and signs it using the crypto functionality of the SIM card applet. The private key is stored in the
 secure storage of the SIM card and can not be retrieved.
 
The sealed data hash is then sent to the **ubirch authentication service** (*"Niomon"*), where it will be verified with
 the previously registered public key and anchored to the blockchain.
 
### LED
The LED on the GPy flashes blue during the initialisation process. If anything goes wrong (or initialisation finished),
 the LED will change colour:

| colour | meaning | what to do |
|--------|---------|------------|
| yellow | couldn't get config from SD card | Make sure the SD card is inserted correctly and has a file named `config.txt` with the API config from the ubirch web UI. The content of the file should look like the example in the previous step including the braces (`{` `}`).
| purple | couldn't connect to network (resets automatically) | Try to find a place with better signal or connect to WIFI instead. (see [here](#configuration))
| red | couldn't acquire PIN to unlock SIM from ubirch backend or other backend related issue | Make sure you have registered the correct IMSI at the [ubirch web UI](https://console.prod.ubirch.com) and you copied the `apiConfig` for your IMSI to the `config.txt` file on the SD card.
| green | it's all good. device is measuring, sending data, sealing and sending data certificate to the ubirch backend| see next chapter |
| orange | sending data or data certificate to the ubirch backend failed |  |
| off | sleeping until the next measurement interval | 

### See the data coming in at the backend
TODO not implemented yet

### Verify the data hash in the backend
TODO not implemented yet

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
        "keyService": "<key registration service URL>",
        "niomon": "<authentication service URL>",
        "data": "<data service URL>",
        "verify": "<verification service URL>",
        "bootstrap": "<bootstrap service URL>",
        "logfile": <true or false>,
        "debug": <true or false>,
        "interval": <measure interval in seconds>
    }
```
There are default values for everything except for the `password`-key, but you can overwrite the default configuration
 by simply adding a key-value pair to your config file on the SD card.

The default connection type is NB-IoT, but if you can not connect to a NB-IoT network, you can change it to WIFI by adding...
 ```json
        "connection": "wifi",
        "networks": {
          "<WIFI SSID>": "<WIFI PASSWORD>"
        },
```
...to your config file and replacing `<WIFI SSID>` with your SSID and `<WIFI PASSWORD>` with your password.

### Log file
If a SD card is present, the device will create a `log.txt`-file on the card and write an error log to it.
 This can be useful if you are having trouble with your TestKit. 
 
 Please feel free to contact us for support any time. We are happy to help!
 ---> HARDWARE@ubirch.com <---