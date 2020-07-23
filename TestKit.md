# Using the UBIRCH TestKit

<img style="float: right" align="right" width="67%" src="pictures/exploded.jpg">

This readme guides you through the process of using the UBIRCH testkit. It assumes that you already have testkit hardware which is programmed and configured with the UBIRCH nano client. This is either because you have received a pre-programmed testkit from UBIRCH or because you have set up your own hardware, e.g. by following the instructions [here](README.md).

### Testkit Components
- 1NCE SIM Card with SIGNiT application
- Pycom GPy
- Pycom Pysense
- Pycom LTE antenna
- micro SD card
- micro USB cable

### What you might also need
- micro SD card writer

### Quick Start
*Note: if you have setup your own testkit hardware, you might have already performed device claiming and flashed a config.json to the internal flash. In this case you can skip this quick start section.*
1. In order to activate your SIM card in the UBIRCH backend, you'll need to *claim* it by registering the **IMSI**, 
a 15 digit number, at the [UBIRCH web UI](https://console.prod.ubirch.com). 

    *If you already know the IMSI of your SIM card, you can skip to the next step.* 

    If the IMSI is unknown, you can find a file `imsi.txt` on the SD card [(1.)](#assembled-testkit)
    in the TestKit which contains the IMSI of your SIM card. (The testkit code must have run at least once.)
    
1. Claim your SIM card identity (IMSI) at the [UBIRCH web UI](https://console.prod.ubirch.com):
    - Login or register if you don't have an account yet.
    - Go to **Things** (in the menu on the left) and click on `+ ADD NEW DEVICE`.
    - Select ID type **IMSI**, enter the IMSI of your SIM card to the **ID** field, 
      add a description for your device (e.g. "TestKit") and click on `register`.
    - Click on your device in the *Your Things* overview and copy the content of the `apiConfig` field.
    
1. Configure your device:
    * Create a file `config.txt` on the SD card and paste the `apiConfig` from the previous step into it. It should look like this:
    ```json
    {
        "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx",
        "keyService": "https://key.prod.ubirch.com/api/keyService/v1/pubkey/mpack",
        "niomon": "https://niomon.prod.ubirch.com/",
        "data": "https://data.prod.ubirch.com/v1/msgPack"
    }
    ```
    * Insert the SD card into the Pysense. [(1.)](#assembled-testkit)
1. Make sure the cellular antenna is attached to the Gpy [(2.)](#assembled-testkit) and power up the TestKit with the micro USB cable. [(3.)](#assembled-testkit)
> WARNING: Using LTE/NB-IoT connectivity without the antenna being attached could damage the development board!

###### Assembled TestKit

<img align="middle" width="67%" src="pictures/assembled.png">

**That's it!** Once powered up, the program on the TestKit starts running automatically.

### How it works
On initial start up, the TestKit will load the configuration from the SD card, connect to the NB-IoT network (APN: *iot.1nce.net*)
 and perform a bootstrap with the UBIRCH backend to acquire the SIM card's PIN via HTTPS.
 Once the SIM card is unlocked, the device will request the x509 certificate from the SIM card's secure storage
 and use it to register the SIM card's public key at the UBIRCH backend. Now the device is ready to send signed 
 UBIRCH Protocol Packages (*UPPs*) to the backend to be anchored to the blockchain.
 
After initialisation, the device will take measurements once a minute and send a data message to the UBIRCH data service.
 The data message contains the device UUID, a timestamp and a map of the sensor data:
 * With a pysense sensor board:
    ```
    {
        "AccPitch": <accelerator Pitch in [deg]>,
        "AccRoll": <accelerator Roll in [deg]>,
        "AccX": <acceleration on x-axis in [G]>,
        "AccY": <acceleration on y-axis in [G]>,
        "AccZ": <acceleration on z-axis in [G]>,
        "H": <relative humidity in [%RH]>,
        "L_blue": <ambient light levels (violet-blue wavelength) in [lux]>,
        "L_red": <ambient light levels (red wavelength) in [lux]>,
        "P": <atmospheric pressure in [Pa]>,
        "T": <board temperature in [°C]>,
        "V": <supply voltage in [V]>
    }
    ```
* With a pytrack sensor board:
    ```
    {
        "AccPitch": <accelerator Pitch in [deg]>,
        "AccRoll": <accelerator Roll in [deg]>,
        "AccX": <acceleration on x-axis in [G]>,
        "AccY": <acceleration on y-axis in [G]>,
        "AccZ": <acceleration on z-axis in [G]>,
        "GPS_lat": <latitude in [deg]>,
        "GPS_long": <longitude in [deg]>,
        "V": <supply voltage in [V]>
    }
    ```

In the next step, a **UBIRCH Protocol Package** (*"UPP"*) will be generated with the unique hash of the serialised data,
 UUID and timestamp, chained to the previous UPP and signed with the SIM card's private key using the 
 crypto functionality of the **SIGNiT** applet. The private key is stored in the secure storage of the SIM card and
 can not be read by the device.
 
The sealed data hash is then sent to the **UBIRCH authentication service** (*"Niomon"*), where it will be verified with
 the previously registered public key and anchored to the blockchain.
 
### LED Color Codes
The LED on the GPy will light up with dim colors during normal operation, i.e. setup, taking measurements, sending, etc.
 If anything goes wrong during the process, the LED will change to a bright color. 
#### Colors During Normal Operation (LED is dimmed)
| color (dimmed) | meaning |
|--------|---------|
| pink | intializing modem and SD card |
| turquoise | loading configuration |
| orange | intializing UBIRCH nano client| 
| blue | measuring sensor data, creating and sealing UPP |
| green | sending sensor data and UPP to backend servers |
| yellow | disconnecting and preparing hardware for sleep |

#### Colors During Error Condition (LED is at full brightness)

| color (bright) | meaning | what to do |
|--------|---------|------------|
| yellow | couldn't get config from SD card | Make sure the SD card is inserted correctly and has a file named `config.txt` with the API config from the UBIRCH web UI. The content of the file should look like the example in the previous step including the braces (`{` `}`).
| purple | couldn't establish network connection (TestKit resets automatically and will try again) | Try to find a place with better signal or connect to WIFI instead. (see [here](#advanced-configuration) how to do that)
| orange | couldn't acquire PIN to unlock SIM from UBIRCH backend or other backend related issue | Make sure you have registered the correct IMSI at the [UBIRCH web UI](https://console.prod.ubirch.com) and you copied the `apiConfig` for your IMSI to the `config.txt` file on the SD card.
| pink | failed to setup modem or communicate with SIM card | Make sure the SIM card is properly inserted to the slot in the Gpy. |
| red | SIM card application error | This should recover by itself. If it does not, or the LED **blinks** red, please contact us. |
| white | unexpected error | Please check the error log on the SD card. |

The TestKit also writes an error log to the SD card. 

### See the data coming in at the backend
TODO not implemented yet

### Verify the data hash in the backend
TODO not implemented yet

### Manually Check Blockchain Anchoring
*This assumes that you have previously setup a console connection to the GPy via the Pymakr console.*
1. While the Pycom is connected and running, and the IDE is open, check the Pymakr console and wait for the hash of 
a data message to appear, e.g.:
    ```
    ++ creating UPP
        UPP: 9623c41005122542132140209225000012dc934ac44024d50ae74e137c049158c6aa4f844f5bd074f196ea311fe6839fa40ed4cc8d7f39bc8c8a4e7105593a76e1f1b86d105cdc8436d171aca1c739e97869bdcdbf8500c4208bef235928a170c58059eef04b4ab29c742b0a127682f54d8a329fd9c4e257f2c4400dccc20526a3c999753e4fa73c200d6a96fc60c1e8e6f4069c7c6d3d066b13376f65da6803cd6e9ca9b655c8946a8e30351bae31bdbf316df3edba5ca86c6cae

        data message hash: i+8jWSihcMWAWe7wS0qynHQrChJ2gvVNijKf2cTiV/I=    
    ```
    Copy the data message hash.

1. Send a POST request to the UBIRCH verification service, e.g. by using **curl** (or any other tool to send POST requests):
    ```
    curl -s -X POST -H "accept: application/json" -H "Content-Type: text/plain" -d "$HASH" "https://verify.prod.ubirch.com/api/upp/verify/anchor"
    ```
    > Replace `$HASH` with the hash copied in step 1


1. The response will list all blockchain anchors containing this measurement certificate. The `txid` (Blockchain 
Transaction ID) of each anchors entry can be used to lookup the entry in the according blockchain explorer (consider 
the `blockchain` and `network_type` attribute to find the right explorer)

### Advanced Configuration
You can set additional configuration options for your device by adding key-value pairs to the `config.txt`-file on the SD card.  (Or to the `config.json` in the internal flash if you have access to that via the pymakr console.)
 These are the available configuration options:
```
{
    "connection": "<'wifi' or 'nbiot', defaults to 'nbiot'>",
    "apn": "<APN for NB IoT connection, defaults to 'iot.1nce.net'>",
    "band": <LTE frequency band (integer or 'null' to scan all bands) , defaults to '8'>,
    "networks": {
        "<your WIFI SSID>": "<your WIFI password>"
    },
    "board": "<pycom expansion board type ['pysense' or 'pytrack'], defaults to 'pysense'>",
    "password": "<auth token for the ubirch backend>",
    "env": "<ubirch backend environment ['demo' or 'prod'], defaults to 'prod'>",
    "keyService": "<key registration service URL, defaults to 'https://key.<env>.ubirch.com/api/keyService/v1/pubkey/mpack'>",
    "niomon": "<authentication service URL, defaults to 'https://niomon.<env>.ubirch.com/'>",
    "data": "<data service URL, defaults to 'https://data.<env>.ubirch.com/v1/msgPack'>",
    "verify": "<verification service URL, defaults to 'https://verify.<env>.ubirch.com/api/upp'>",
    "bootstrap": "<bootstrap service URL, defaults to 'https://api.console.<env>.ubirch.com/ubirch-web-ui/api/v1/devices/bootstrap'>",
    "debug": <flag to enable extended debug console output [true or false], defaults to 'false'>,
    "interval": <measure interval in seconds, defaults to '60'>
}
```
There are default values for everything except for the `password`-key, but you can overwrite the default configuration
 by simply adding a key-value pair to your config file on the SD card (or in the internal flash).

The default connection type is NB-IoT, but if you can not connect to a NB-IoT network, you can change it to WIFI by adding...
```
    "connection": "wifi",
    "networks": {
      "<WIFI_SSID>": "<WIFI_PASSWORD>"
    },
```
...to your config file and replacing `<WIFI_SSID>` with your SSID and `<WIFI_PASSWORD>` with your password.

### Log file
If a SD card is present, the device will create a `log.txt`-file on the card and write an error log to it.
 This can be useful if you are having trouble with your TestKit. If there is no SD card, the device will store the 
 log-file in the GPy's internal flash memory. You can read it by downloading the project files from your board's
 flash memory using the Pymakr `DOWNLOAD` button, if you have configured Pymakr.

### Support
Please feel free to contact [our helpdesk](https://ubirch.atlassian.net/servicedesk/customer/portal/1) for support.
