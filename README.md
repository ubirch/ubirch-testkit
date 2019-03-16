# ubirch-protocol for micropython

This example is targeted at micropython, specifically Pycom modules.
A special build is required and available in the releases and has everything the
official Pycom build contains plus an `Ed25510` crypto implementation.

Download [Atom](https://atom.io) and install the [Pymakr](https://atom.io/packages/pymakr)
plugin to get started.

The example code is made for any Pycom module sitting on a Pysense.

* checkout out this repository
  ```
  $ git checkout https://github.com/ubirch/example-micropython.github
  ```
* Add directory to Atom using `File` -> `Add Project Folder`
* Use the [Pycom Firmware Upgrader](https://pycom.io/downloads/#firmware) to
  flash the correct binary for your board.
* Edit [src/settings.py](src/settings.py) and add your wifi SSID and password  
* If the Pymakr plugin is loaded, you should have a terminal at the bottom
  with buttons to upload and run scripts. Simply Upload the code to get going.

# Visualization

To see data in our backend, go to [ubirch](https://ubirch.dev.ubirch.com) and
register. Ping [@thinkberg](https://twitter.com/thinkberg) to enable your account.

Create a new device with the device UUID that is displayed when running the
code. If everything is okay, it should start sending temperature and humidity
as `valueA` and `valueB`.
