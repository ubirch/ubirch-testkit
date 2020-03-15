# ubirch-protocol for micropython

This example is targeted at micropython, specifically Pycom modules. 
The example code is made for any Pycom module sitting on a **Pysense** or **Pytrack**.

## Setup Environment
* Download [Atom](https://atom.io) and install the [Pymakr](https://atom.io/packages/pymakr)
plugin. If the Pymakr plugin is loaded, you should have a terminal at the bottom
  with buttons to upload and run scripts.
* Checkout out this repository
  ```
  $ git checkout https://github.com/ubirch/example-micropython.git
  ```
* Add the directory to Atom using `File` -> `Add Project Folder`

### Setting up SIM card with SIGNiT application
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

 
 ## Configuration
 TODO