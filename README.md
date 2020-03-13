# ubirch-protocol for micropython

This example is targeted at micropython, specifically Pycom modules. 
The example code is made for any Pycom module sitting on a **Pysense** or **Pytrack**.
There are two crypto implementations that can be used with the example . Either a SIM card with SIGNiT application or
 a firmware with an `Ed25510` crypto implementation. 

For the latter, a special build is required which is available in the releases and has everything the official Pycom
 build contains plus the required `Ed25510` crypto implementation. Use the [Pycom Firmware Upgrader](https://pycom.io/downloads/#firmware)
 to flash the correct binary for your board.

## Setup
* Download [Atom](https://atom.io) and install the [Pymakr](https://atom.io/packages/pymakr)
plugin. If the Pymakr plugin is loaded, you should have a terminal at the bottom
  with buttons to upload and run scripts.
* Checkout out this repository
  ```
  $ git checkout https://github.com/ubirch/example-micropython.git
  ```
* Add the directory to Atom using `File` -> `Add Project Folder`

### Setting up SIM card with SIGNiT application (skip if you are using the Ed25510 crypto implementation)
* Register your SIM card's IMSI at the [ubirch web UI](https://console.demo.ubirch.com) and get your
 authentication token for the ubirch backend.
    * Once logged in, go to **Things** (in the menu on the left) and click on **ADD NEW DEVICE**
    * Paste the IMSI in the **ID** field and click **register**
    * Next, click on your device and copy the *apiConfig*.
    
* Configure your device
    * Create a file *config.json* in the `src` directory in your project and paste the *apiConfig* into it.
    * Add configuration for the kind of expansion board you are using with the key `"board"`.
        Your config file should then look like this:
        ```json
        {
          "board": "<'pysense' or 'pytrack'>",
          "password": "<auth token for the ubirch backend>",
          "keyService": "<key registration service URL>",
          "niomon": "<authentication service URL>",
          "data": "<data service URL>"
        }
        ```
        > Per default the device will try to establish a `NB-IoT` (LTE) connection. The default APN is `"iot.1nce.net"`. For more configuration options, see [here](#configuration).
* Upload the file to your device using the Pymakr `UPLOAD` button and you're good to go.

### Setting up Ed25510 crypto implementation (skip if you are using SIM card with SIGNiT application)
* Upload the code to your device using the Pymakr `UPLOAD` button.
* The device should now start printing output to in the Pymakr console. Copy the UUID displayed in the console window.
* Register your device UUID at the [ubirch web UI](https://console.demo.ubirch.com) and get your
 authentication token for the ubirch backend.
    * Once logged in, go to **Things** (in the menu on the left) and click on **ADD NEW DEVICE**
    * Paste the UUID in the **ID** field and click **register**
    * Next, click on your device and copy the *apiConfig*.
    
* Configure your device
    * Create a file *config.json* in the `src` directory in your project and paste the *apiConfig* into it.
    * Add configuration for the crypto implementation, kind of connection and expansion board you are using.
        
        If you want to connect to a WIFI network, add your SSID and WIFI password.
         If you want to use a LTE connection, add the APN.
          (You will need a GPy with a SIM card for that.) 
    
       It should then look like this:
        ```json
        {
          "sim": false,
          "connection": "<'wifi' or 'nbiot'>",
          "networks": {
            "<WIFI SSID>": "<WIFI PASSWORD>"
          },
          "apn": "<APN for NB-IoT connection>",
          "board": "<'pysense' or 'pytrack'>",
          "password": "<auth token for the ubirch backend>",
          "keyService": "<key registration service URL>",
          "niomon": "<authentication service URL>",
          "data": "<data service URL>"
        }
        ```
         > For more configuration options, see [here](#configuration).
* Upload the file to the board and you're good to go. 
 
 ## Configuration
 TODO