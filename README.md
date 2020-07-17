# UBIRCH Testkit

A micropython client for the UBIRCH protocol on a SIM

The ubirch testkit is a combination of hardware based on pycom hardware modules (we use GPy and Pysense) and micropython example code to demonstrate the usage of the UBIRCH protocol. It allows for easy use and evaluation of the 'blockchain on a SIM' application which implements UBIRCH funtionality inside of a SIM card. The SIM card needs to have the 'SIGNiT' applet for cryptographic functionality present (e.g. a 1nce SIM with ubirch functionality enabled).

**If you have already received pre-programmed testkit hardware from UBIRCH, you can directly head over to [the TestKit manual](TestKit.md) and follow the Quick Start for rapid UBIRCHING.**

If you want to setup your own testkit hardware, read on.

## Setting up your own testkit hardware
### Required hardware
Please acquire the following hardware:

- 1NCE SIM Card with SIGNiT application
- Pycom GPy
- Pycom Pysense
- Pycom LTE antenna
- micro SD card (optional)
- micro USB cable
 
### Update your devices
Before you start, you should follow these instructions to update your hardware:
* [Pysense/Pytrack firmware update](https://docs.pycom.io/pytrackpysense/installation/firmware/)
* [device assembling](https://docs.pycom.io/gettingstarted/connection/gpy/)
* [GPy firmware update](https://docs.pycom.io/gettingstarted/installation/firmwaretool/)
* [modem firmware update](https://docs.pycom.io/tutorials/lte/firmware/) **Make sure you'll get the NB-IoT firmware for the modem!**

Please do not skip the modem firmware update to **switch the GPy from CAT-M1 to the NB-IoT version**. Without this, there will be no connectivity with the SIM card.
 
### Set up Environment
1. Get Pymakr for *Atom* or *Visual Studio Code*
    - Download and install [**Atom**](https://atom.io) or [**Visual Studio Code**](https://code.visualstudio.com/download) 
    - Install the Pymakr plugin [for Atom](https://docs.pycom.io/pymakr/installation/atom/) or [for VSCode](https://docs.pycom.io/pymakr/installation/vscode/).
     If Pymakr is loaded, you should have a terminal at the bottom of your IDE with buttons to upload and run code.

1. Clone this repository or download a release zip file
      ```
      $ git clone https://github.com/ubirch/ubirch-testkit.git
      ```

1. Add the project directory to your IDE's working directory:
    - Atom: `File` -> `Add Project Folder`
    - VS Code: `File` -> `Open Folder`

### Assemble your device:
1. Insert SIM card to the underside of the GPy.
2. Mount the GPy on the expansion board (pysense or pytrack). The LED on the GPy goes over the micro USB port on the expansion board.
3. Attach the cellular antenna to the Gpy next to LED on the GPy.
    > Using LTE/NB-IoT connectivity without the antenna being attached could damage your device!

### Set up SIM card and device
1. In order to activate your SIM card in the UBIRCH backend, you'll need to *claim* it by registering the **IMSI**, 
a 15 digit number, at the [UBIRCH web UI](https://console.prod.ubirch.com). If you already know the IMSI of your SIM 
card, you can skip to the next step. 

    If the IMSI is unknown:
    - connect your assembled Pycom device with the inserted SIM card to your computer via USB 
    and watch Pymakr console in your IDE. If it worked, you should see the following output:
      ```
      Connecting to /dev/ttyACM0...
      
      >>> 
      ```
    - Press the Pymakr `UPLOAD` button. This transfers the example code into the GPy's internal flash.
    - Wait for the IMSI to be printed to the console
        ```
        >> getting IMSI
        IMSI: 987654321098765
        ```
    - Copy the IMSI

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
        > Per default the device will try to establish a `NB-IoT` (LTE) connection. The default APN is `"iot.1nce.net"`. For more configuration options, see [the TestKit manual](TestKit.md).

1. Upload the program to your device again to transfer the `config.json` to the internal flash of the GPy.
    - Connect the Pycom device to your computer via USB and watch Pymakr console in your IDE. If it worked, you should see the following output:
      ```
      Connecting to /dev/ttyACM0...
      
      >>> 
      ```
    - Press the Pymakr `UPLOAD` button.

You should now see the testkit code running in the pymakr console and the boards LED cycle through different colors. You can now head over to [the TestKit manual.](TestKit.md) to learn how to use your testkit.

### Support
Please feel free to contact [our helpdesk](https://ubirch.atlassian.net/servicedesk/customer/portal/1) for support.
