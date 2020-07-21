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
- micro SD card
- micro USB cable
 
### Update GPy/Pysense Firmware
Before you start, you should follow these instructions to update your pycom boards:
1. [Update the Pysense firmware](https://docs.pycom.io/pytrackpysense/installation/firmware/)
    - Please follow the instructions on the linked site.
2. [Assemble the Pysense and GPy](https://docs.pycom.io/gettingstarted/connection/gpy/) 
    - Please refer to the Pysense/Pytrack/Pyscan tab on the linked page for the correct assembly. The RGB LED of the GPy should be on the same side as the Pysense's micro USB connector when you're done.
    - **Also, do not forget to connect the antenna, the GPy might be damaged otherwise.** The antenna is connected to the port next to the RGB LED and reset button on the GPy.    
3. [Update the GPy firmware](https://docs.pycom.io/gettingstarted/installation/firmwaretool/)
    - Please download the firmware update tool from the linked webpage and follow the tool's on-screen instructions
    - Please choose the following settings:
        - port: the serial port where your GPy board is connected
        - high speed transfer: yes
        - advanced settings: no
        - flash from local file: no
        - type: pybytes
        - force update pybytes registration: no
        - enable pybytes: no
        - if asked for the board type, select 'GPy'

You can now proceed to set up your enviroment so you can upload code to the GPy and access it using the 'Pymakr' console.
 
### Set up Environment
1. Get Pymakr for *Atom* or *Visual Studio Code*
    - Download and install [**Atom**](https://atom.io) or [**Visual Studio Code**](https://code.visualstudio.com/download) 
    - Install the Pymakr plugin [for Atom](https://docs.pycom.io/pymakr/installation/atom/) or [for VSCode](https://docs.pycom.io/pymakr/installation/vscode/).

1. Clone this repository in a directory of your choice or download and extract a [release zip file](https://github.com/ubirch/ubirch-testkit/releases).
      ```
      $ git clone https://github.com/ubirch/ubirch-testkit.git
      ```

1. Add the project directory to your IDE's working directory:
    - Atom: `File` -> `Add Project Folder`
    - VS Code: `File` -> `Open Folder`
    
 You should now have a Pymakr terminal at the bottom of your IDE with buttons to upload and run code. You should now also see the testkit code files (.py) in your IDE's folder view. 

### Update the Modem Firmware
Please do not skip the modem firmware update to **switch the GPy from CAT-M1 to the NB-IoT version**. Without this, there will be no connectivity with the SIM card.

Please perform an upgrade of the modem firmware as shown in [this tutorial video](https://www.youtube.com/watch?v=jNbYhNHzma0). The main steps are oulined below.

1. Acquire the modem firmware files from the Pycom website
    1. Acquire the firmware password: In order to download the password-protected firmware files, register on [forum.pycom.io](http://forum.pycom.io). Then you can find the password in the thread "Announcements & News –> Announcements for members only –> the Firmware Files for the Sequans LTE modem are now secured"
    2. Download the latest modem firmware from [here](https://software.pycom.io/downloads/sequans.html). **Please make sure you'll get the NB-IoT firmware for the modem!**
2. Extract/copy the .dup and .elf files from the zip file onto an SD card, and insert the SD card into the pysense. The files should be placed in the root folder.
3. Connect to your Pymakr console. You might have to click the 'Pymakr Console' button to toggle the board connection, it should show a checkmark and you should see ```>>>``` in the Pymakr terminal.
4. Execute the firmware update by running the commands detailed in the tutorial video in the Pymakr console. If you can't find a matching upgdiff_XXXXX-to-YYYYY.dup for your current firmware version in the zip file, please use the NB1-YYYYY.dup and updater.elf file for the upgrade (e.g. ```sqnsupgrade.run('/sd/NB1-YYYYY.dup','/sd/updater.elf')```). If you run into problems, try using a different SD card, a different/shorter USB cable or different USB port with sufficient power.

    Example output:
    ```
    >>> import sqnsupgrade
    >>> sqnsupgrade.info()
    <<< Welcome to the SQN3330 firmware updater [1.2.6] >>>
    >>> GPy with firmware version 1.20.2.rc10
    Your modem is in application mode. Here is the current version:
    UE5.0.0.0d
    LR5.1.1.0-43818

    IMEI: XXXXXXXXX
    >>> sqnsupgrade.run('/sd/NB1-41019.dup','/sd/updater.elf')
    <<< Welcome to the SQN3330 firmware updater [1.2.6] >>>
    >>> GPy with firmware version 1.20.2.rc10
    Attempting AT auto-negotiation...
    Session opened: version 1, max transfer 2048 bytes
    Sending 371307 bytes: [########################################] 100%
    Waiting for updater to load...
    Attempting AT wakeup...
    Session opened: version 1, max transfer 8192 bytes
    Sending 5835531 bytes: [########################################] 100%
    Waiting for modem to finish the update...
    <<<=== DO NOT DISCONNECT POWER ===>>>
    Resetting...................................
    Your modem has been successfully updated.
    Here is the current firmware version:

    UE6.0.0.0
    LR6.0.0.0-41019

    IMEI: XXXXXXXXX
    True
    >>>
    ```
5. Reset the modem settings to default via the Pymakr console. This will take about 30 seconds and finish with a board reset.
    ```
    >>> from network import LTE
    >>> lte = LTE()
    >>> lte.factory_reset()
    ```

For additional help, you can also refer to pycom's [wiki](https://docs.pycom.io/tutorials/lte/firmware/) 

### Insert the SIM
1. Unplug all power sources to the GPy/Pysense board
1. Remove the GPy from the Pysense board
1. Insert SIM card to the underside of the GPy.
1. Re-mount the GPy on the expansion board (pysense or pytrack). The LED on the GPy goes over the micro USB port on the expansion board.
1. Make sure the cellular antenna is still attached to the Gpy next to the RGB LED and reset button.
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
