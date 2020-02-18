# ubirch-protocol for micropython

This example is targeted at micropython, specifically Pycom modules.
A special build is required and available in the releases and has everything the
official Pycom build contains plus an `Ed25510` crypto implementation.

Download [Atom](https://atom.io) and install the [Pymakr](https://atom.io/packages/pymakr)
plugin to get started.

The example code is made for any Pycom module sitting on a Pysense or Pytrack.

* checkout out this repository
  ```
  $ git checkout https://github.com/ubirch/example-micropython.git
  ```
* Add the directory to Atom using `File` -> `Add Project Folder`
* Use the [Pycom Firmware Upgrader](https://pycom.io/downloads/#firmware) to
  flash the correct binary for your board.
* If the Pymakr plugin is loaded, you should have a terminal at the bottom
  with buttons to upload and run scripts. Simply upload the code to get going.
* Take note of the UUID displayed in the console window
* Go to https://console.demo.ubirch.com to register your device:
    * Once logged in, go to **Things** (in the menu on the left) and click on **ADD NEW DEVICE**
    * paste the UUID in the **hwDeviceId** field
    * click **create**
* Next, click on your device, copy the apiConfig, create src/config.json in your project
  and paste the apiConfig into it.
* Add configuration for the kind of connection and expansion board you are using.

   It should then look like this:
    ```json
    {
      "type": "<'pysense' or 'pytrack'>",
      "connection": "<'wifi' or 'nbiot'>",
      "networks": {
        "<WIFI SSID>": "<WIFI PASSWORD>"
      },
      "apn": "<APN for NB-IoT connection>",
      "password": "<password for ubirch auth and data service>",
      "keyService": "<URL of key registration service>",
      "niomon": "<URL of authentication service>",
      "data": "<URL of data service>"
    }
    ```
* Upload the file to the board again and you're good to go. 
 