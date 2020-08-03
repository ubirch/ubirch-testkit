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
    in the TestKit which contains the IMSI of your SIM card. If the file does not exist, please plug in the testkit for a minute so that it can be created. You can unplug the testkit to remove the SD when the LED stops changing colors or when it turns off.
    
1. Claim your SIM card identity (IMSI) at the [UBIRCH web UI](https://console.prod.ubirch.com):
    - Login or register if you don't have an account yet.
    - Go to **Things** (in the menu on the left) and click on `+ ADD NEW DEVICE`.
    - In the resulting form enter the following data:
        - Select ID type **IMSI**
        - Enter the IMSI of your SIM card to the **ID** field
        - Add a **description** for your device (e.g. "TestKit")
        - Enter the **tag** matching your sensor board, usually `pysense`. Please **make sure you enter the tag correctly as otherwise there will be no display of the sensor data** in the console.
    - Click on `register`.
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

### Verify the Sensor Data  (UBIRCH console)
Log in to the ubirch console and head to the [things list](https://console.prod.ubirch.com/devices/list). Click the device you want to view and select the "data" tab. You should now see a graphical representation of the sensor data of the testkit. If your device doesn't have the data tab, make sure that you added the correct tag for your sensor board (`pysense` or `pytrack`) to the things settings when you added it. You can verify this under the "ThingsSettings" tab.

### Display the Last Received Hashes  (UBIRCH console)
Log in to the ubirch console and head to the [things list](https://console.prod.ubirch.com/devices/list). Click the device you want to view and select the "RecentHashes" tab. You should now see a list of the last received hashes. You can click the verify button to be transferred to the verification page (see next section). Keep in mind that anchoring might take some time, so it might be a good idea to select a hash from the bottom of the list for verification. 

### Verify the Blockchain Anchoring (UBIRCH console)
Log in to the ubirch console and head to the ["verification" page](https://console.prod.ubirch.com/verification/). Insert the hash of the data message you want to verify in the search field, e.g. `Yx/M1vxy/RrdpYENQg/dHj4IFhIMPPS4W7CYapfjugY=` . To obtain a hash of your device, see either the "RecentHashes" tab after selecting your device in the [things list](https://console.prod.ubirch.com/devices/list), or if you have setup a pymakr console, you can watch the messages for the data hash. If the lookup is successful, you can choose either a graphical or a JSON representation of the anchoring of that UPP. If the data is empty. anchoring might simply not have finished yet, please try again in 10 minutes. For the graphical representation, use scrollwheel and click+drag to navigate. Blockchain anchors in the graph such as IOTA, Ethereum, etc., can be clicked to view them in an online blockchain explorer.

### Manually Check Blockchain Anchoring
*This assumes that you have previously setup a console connection to the GPy via the Pymakr console.*
1. While the Pycom is connected and running, and the IDE is open, check the Pymakr console and wait for the hash of 
a data message to appear, e.g.:
    ```
    ++ creating UPP
        UPP: 9623c41005122542132140209225000013adf293c440590b27d80148bd997039c50683376487ecae4792e92a9f453c67671e2337f1fb8f884919477cc210a02217182d9b505ee2ffc498ce25aaa9f258dcf7e7e0fed900c420631fccd6fc72fd1adda5810d420fdd1e3e0816120c3cf4b85bb0986a97e3ba06c440e7ae1724014854061e2454dae38950eb1334eef887e8004deab224b9994dd5b05265e1dac34d9719adde97f12ce786dad5d54ee2e0e9719656e5ce1507f56158

        data message hash: Yx/M1vxy/RrdpYENQg/dHj4IFhIMPPS4W7CYapfjugY=
    ```
    Copy the data message hash.

1. To see if the UPP arrived at the backend, send a POST request to the UBIRCH verification service, e.g. by using **curl** (or any other tool to send POST requests). The use of the jq command ('| jq .') is optional.:
    > Replace the value after `HASH=` with the hash copied in step 1.
    ```    
    HASH=Yx/M1vxy/RrdpYENQg/dHj4IFhIMPPS4W7CYapfjugY=
    curl -s -X POST https://verify.prod.ubirch.com/api/upp -d "$HASH" | jq .
    ```
    Example output:
    ```
    {
        "upp": "liPEEAUSJUITIUAgkiUAABOt8pPEQFkLJ9gBSL2ZcDnFBoM3ZIfsrkeS6SqfRTxnZx4jN/H7j4hJGUd8whCgIhcYLZtQXuL/xJjOJaqp8ljc9+fg/tkAxCBjH8zW/HL9Gt2lgQ1CD90ePggWEgw89LhbsJhql+O6BsRA564XJAFIVAYeJFTa44lQ6xM07viH6ABN6rIkuZlN1bBSZeHaw02XGa3el/Es54ba1dVO4uDpcZZW5c4VB/VhWA==",
        "prev": null,
        "anchors": null
    }
    ```
    If the response is empty, the UPP has not arrived at the backend yet.

1. To check blockchain anchoring, please wait about 10 minutes for your UPP to be anchored. Afterwards, send a POST request to the UBIRCH verification service, e.g. by using **curl** (or any other tool to send POST requests). The use of the jq command ('| jq .') is optional.:
    > Replace the value after `HASH=` with the hash copied in step 1.
    ```
    HASH=Yx/M1vxy/RrdpYENQg/dHj4IFhIMPPS4W7CYapfjugY=
    curl -s -X POST https://verify.prod.ubirch.com/api/upp/verify/anchor -d "$HASH" | jq .
    ```
    Example output:
    ```
    {
        "upp": "liPEEAUSJUITIUAgkiUAABOt8pPEQFkLJ9gBSL2ZcDnFBoM3ZIfsrkeS6SqfRTxnZx4jN/H7j4hJGUd8whCgIhcYLZtQXuL/xJjOJaqp8ljc9+fg/tkAxCBjH8zW/HL9Gt2lgQ1CD90ePggWEgw89LhbsJhql+O6BsRA564XJAFIVAYeJFTa44lQ6xM07viH6ABN6rIkuZlN1bBSZeHaw02XGa3el/Es54ba1dVO4uDpcZZW5c4VB/VhWA==",
        "prev": "liPEEAUSJUITIUAgkiUAABOt8pPEQFCoBTkqdAmNqFqvs0b7XLoMjcfkaeCCzzbMme40luLRMn54qbdyYipLGAK1w2pYqmjbrGnpmrjrtalolsguw70AxCDDZlMunRg0ItIj0cCn55WGpfZPoJGcL8i80/HL+FCutcRAWQsn2AFIvZlwOcUGgzdkh+yuR5LpKp9FPGdnHiM38fuPiEkZR3zCEKAiFxgtm1Be4v/EmM4lqqnyWNz35+D+2Q==",
        "anchors": [
            {
            "label": "PUBLIC_CHAIN",
            "properties": {
                "public_chain": "IOTA_MAINNET_IOTA_MAINNET_NETWORK",
                "hash": "HNWXRY9OROVMDBDURUUVYILRVURRWIF9DNXYBFABPOWNKYYEGDJUROIZA9GVQNYCGWGZUXJFHPZ9Z9999",
                "timestamp": "2020-07-23T16:13:54.381Z",
                "prev_hash": "94bcb97a449d7e28b31253db2a291d035f64ec70332b94220dfc0a3f07ed2caf2f14fc1fe8ae4e898b23c82c6355bc3367dfb6323022ec1a4fc660f7802068e6"
            }
            },
            {
            "label": "PUBLIC_CHAIN",
            "properties": {
                "public_chain": "ETHEREUM-CLASSIC_MAINNET_ETHERERUM_CLASSIC_MAINNET_NETWORK",
                "hash": "0x6ec75539792d92bdf1cb1cfb0ce89d1ce9b369ea1f43e86b0c7a6def2d06ab85",
                "timestamp": "2020-07-23T16:15:02.953Z",
                "prev_hash": "94bcb97a449d7e28b31253db2a291d035f64ec70332b94220dfc0a3f07ed2caf2f14fc1fe8ae4e898b23c82c6355bc3367dfb6323022ec1a4fc660f7802068e6"
            }
            }
        ]
    }
    ```
    If the "anchors" field is empty, this UPP might not have been anchored yet, please try again later.     

1. The anchoring response lists all blockchain anchors containing this measurement certificate. The information can be used to lookup the entry in a suitable blockchain explorer. Consider the name of the blockchain e.g. Ethereum, IOTA, etc., to find a suitable explorer and perform the lookup using the hash.

### Advanced Configuration
You can set additional configuration options for your device by adding key-value pairs to the `config.txt`-file on the SD card.  (Or to the `config.json` in the internal flash if you have access to that via the pymakr console.)
 These are the available configuration options:
```
{
    "connection": "<'wifi' or 'nbiot', defaults to 'nbiot'>",
    "apn": "<APN for NB IoT connection, defaults to 'iot.1nce.net'>",
    "band": <LTE frequency band (integer or 'null' to scan all bands) , defaults to '8'>,
    "nbiot_attach_timeout": <timeout after which the nb-iot attach is aborted and board reset, defaults to 60>,
    "nbiot_connect_timeout": <timeout after which the nb-iot connect is aborted and board reset, defaults to 60>,
    "nbiot_extended_attach_timeout": <extended attach timeout, used when not coming from sleep (after power-on, errors), defaults to 900>,
    "nbiot_extended_connect_timeout": <extended connect timeout, used when not coming from sleep (after power-on, errors), defaults to 60>,
    "watchdog_timeout": <if execution takes longer than this in total, the board is reset, defaults to 300>,
    "watchdog_extended_timeout": <extended watchdog timeout, used when not coming from sleep (after power-on, errors), defaults to 960>,
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
