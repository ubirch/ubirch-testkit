# Micropython client for the UBIRCH protocol on a SIM
This example is targeted at micropython, specifically Pycom modules. 
The micropython example code uses a SIM Card with SIGNiT applet for cryptographic functionality. For that reason,
 it is necessary to use the Pycom **GPy**, which includes a modem. The user can choose **Pysense** or **Pytrack**
 for the expansion board.
 
 If you have a UBIRCH TestKit, you can head over to the [TestKit manual](TestKit.md) and follow the Quick Start
 for rapid UBIRCHING.
 
### Prepare your device
Before you start, you should follow these instructions:
* [Pysense/Pytrack firmware update](https://docs.pycom.io/pytrackpysense/installation/firmware/)
* [device assembling](https://docs.pycom.io/gettingstarted/connection/gpy/)
* [GPy firmware update](https://docs.pycom.io/gettingstarted/installation/firmwaretool/)
* [modem firmware update](https://docs.pycom.io/tutorials/lte/firmware/) **Make sure you'll get the NB-IoT firmware for the modem!**
 
### Set up Environment
1. Get Pymakr for *Atom* or *Visual Studio Code*
    - Download and install [**Atom**](https://atom.io) or [**Visual Studio Code**](https://code.visualstudio.com/download) 
    - Install the Pymakr plugin [for Atom](https://docs.pycom.io/pymakr/installation/atom/) or [for VSCode](https://docs.pycom.io/pymakr/installation/vscode/).
     If Pymakr is loaded, you should have a terminal at the bottom of your IDE with buttons to upload and run code.

1. Checkout out this repository
      ```
      $ git checkout https://github.com/ubirch/example-micropython.git
      ```

1. Add the project directory to your IDE's working directory:
    - Atom: `File` -> `Add Project Folder`
    - VS Code: `File` -> `Open Folder`

### Set up SIM card and device
1. Claim your SIM card identity (IMSI) at the [UBIRCH web UI](https://console.prod.ubirch.com):
    - Login or register if you don't have an account yet.
    - Go to **Things** (in the menu on the left) and click on `+ ADD NEW DEVICE`.
    - Select ID type **IMSI**, enter the IMSI of your SIM card to the **ID** field, 
      add a description for your device (e.g. "TestKit") and click on `register`.
    - Click on your device in the *Your Things* overview and copy the content of the `apiConfig` field.
    
1. Configure your device
    * Create a file `config.json` in the `src` directory of the project and paste the `apiConfig` into it.
    * Add configuration for the kind of expansion board you are using with the key `"board"` and the value `"pysense"` or `"pytrack"`.
        Your config file should then look like this:
        ```json
        {
          "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx",
          "keyService": "https://key.prod.ubirch.com/api/keyService/v1/pubkey/mpack",
          "niomon": "https://niomon.prod.ubirch.com/",
          "data": "https://data.prod.ubirch.com/v1/msgPack",
          "board": "<'pysense' or 'pytrack'>"
        }
        ```
        > Per default the device will try to establish a `NB-IoT` (LTE) connection. The default APN is `"iot.1nce.net"`. For more configuration options, see [here](#configuration).

1. Upload the program to your device
    - Assemble your device:
        - insert SIM card to GPy
        - mount the GPy on the expansion board (LED on the GPy goes over the micro USB port on the expansion board)
        - attach the cellular antenna to the Gpy (next to LED on the GPy)
            > Using LTE/NB-IoT connectivity without the antenna being attached could damage your device!
    - Connect the Pycom device to your computer via USB and watch Pymakr console in your IDE. If it worked, you should see the following output:
      ```
      Connecting to /dev/ttyACM0...
      
      >>> 
      ```
    - Press the Pymakr `UPLOAD` button.

### Program flow
After upload, the program starts running on the device. On initial start, the device will perform a bootstrap
 with the UBIRCH backend to acquire the SIM card's PIN. Once the SIM card is unlocked, the device will request
 the x509 certificate from the SIM card's secure storage and use it to register the SIM card's public key at
 the UBIRCH backend. After that, it will frequently measure the following data...
* pysense:
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
        "T": <external temperature in [°C]>,
        "V": <supply voltage in [V]>
    }
    ```
* pytrack:
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
...and send it to the UBIRCH data service. 

It then packs the SHA 256 hash of the data into a signed and chained UPP (Ubirch Protocol Package) which is the certificate
 of the data's authenticity, and sends it to the UBIRCH public blockchain based authentication and timestamping service.


## Check Blockchain Anchoring
1. While the Pycom is connected and running, and the IDE is open, check the Pymakr console and wait for the hash of 
a data message to appear, e.g.:
    ```
    ** data message hash: kk/3ZIvK4SOPZXYnSoaFRt1n7ncC+9RxWnFXPO9tzdk=
    ```
    Copy the hash.

1. Send a POST request to the UBIRCH verification service, e.g. by using **curl** (or any other tool to send POST requests):
    ```
    curl -s -X POST -H "accept: application/json" -H "Content-Type: text/plain" -d "$HASH" "https://verify.prod.ubirch.com/api/upp/verify/anchor"
    ```
    > Replace `$HASH` with the hash copied in step 1


1. The response will list all blockchain anchors containing this measurement certificate. The `txid` (Blockchain 
Transaction ID) of each anchors entry can be used to lookup the entry in the according blockchain explorer (consider 
the `blockchain` and `network_type` attribute to find the right explorer)

### Configuration
These are the configuration options:
```
{
    "connection": "<'wifi' or 'nbiot', defaults to 'nbiot'>",
    "apn": "<APN for NB IoT connection, defaults to 'iot.1nce.net'>",
    "networks": {
        "<your WIFI SSID>": "<your WIFI password>"
    },
    "board": "<pycom expansion board type ('pysense' or 'pytrack'), defaults to 'pysense'>",
    "password": "<auth token for the ubirch backend>",
    "env": "<ubirch backend environment ('dev', 'demo' or 'prod'), defaults to 'prod'>",
    "keyService": "<key registration service URL, defaults to 'https://key.<env>.ubirch.com/api/keyService/v1/pubkey/mpack'>",
    "niomon": "<authentication service URL, defaults to 'https://niomon.<env>.ubirch.com/'>",
    "data": "<data service URL, defaults to 'https://data.<env>.ubirch.com/v1/msgPack'>",
    "verify": "<verification service URL, defaults to 'https://verify.<env>.ubirch.com/api/upp'>",
    "bootstrap": "<bootstrap service URL, defaults to 'https://api.console.<env>.ubirch.com/ubirch-web-ui/api/v1/devices/bootstrap'>",
    "logfile": <flag to enable error logging to file (true or false), defaults to 'true'>,
    "debug": <flag to enable extended debug console output (true or false), defaults to 'false'>,
    "interval": <measure interval in seconds, defaults to '60'>
}
```
There are default values for everything except for the `password`-key, but you can overwrite the default configuration
 by adding a key-value pair to your config file.

The default connection type is NB-IoT, but if you can not connect to a NB-IoT network, you can change it to WIFI by adding...
```
    "connection": "wifi",
    "networks": {
      "<WIFI_SSID>": "<WIFI_PASSWORD>"
    },
```
...to your config file and replacing `<WIFI_SSID>` with your SSID and `<WIFI_PASSWORD>` with your password.

Per default, the device will write an error log to a file. If a SD card is present, the device will create
 a `log.txt`-file on the card and write the log to it. If there is no SD card, the device will store the 
 log-file to the Pycom's flash memory. You can read it by downloading the project files from your board's
 flash memory using the Pymakr `DOWNLOAD` button.

### Support
Please feel free to contact [our helpdesk](https://ubirch.atlassian.net/servicedesk/customer/portal/1) for support.