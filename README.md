# ubirch-protocol for micropython

This example is targeted at micropython, specifically Pycom modules.
A special build is required and available in the releases and has everything the
official Pycom build contains plus an `Ed25510` crypto implementation.

Download [Atom](https://atom.io) and install the [Pymakr](https://atom.io/packages/pymakr)
plugin to get started.

The example code is made for any Pycom module sitting on a Pysense.

* checkout out this repository
  ```
  $ git checkout https://github.com/ubirch/example-micropython.git
  ```
* Add directory to Atom using `File` -> `Add Project Folder`
* Use the [Pycom Firmware Upgrader](https://pycom.io/downloads/#firmware) to
  flash the correct binary for your board.
* Create src/boot.json and add your wifi SSID and password: 
    ```json
    {
      "ssid": "SSID",
      "password": "password",
      "timeout": 5000,
      "retries": 10
    }
    ``` 
* Create src/settings.json and add the Cumulocity bootstrap password to connect:
    ```json
    {
        "type": "pysense",
        "bootstrap": {
            "authorization": "Basic XXXXX",
            "tenant": "ubirch",
            "host": "management.cumulocity.com"
        },
        "interval": 60
    }
    ```
* If the Pymakr plugin is loaded, you should have a terminal at the bottom
  with buttons to upload and run scripts. Simply Upload the code to get going.
* Take note of the UUID displayed in the console window, go to https://ubirch.cumulocity.com
  and register your device
* Accept the registration and you're good to go  
 