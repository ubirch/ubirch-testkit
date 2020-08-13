# UBIRCH Testkit

A micropython client for the UBIRCH protocol on a SIM

The ubirch testkit is a combination of hardware based on pycom hardware modules (we use GPy and Pysense) and micropython example code to demonstrate the usage of the UBIRCH protocol. It allows for easy use and evaluation of the 'blockchain on a SIM' application which implements UBIRCH funtionality inside of a SIM card. The SIM card needs to have the 'SIGNiT' applet for cryptographic functionality present (e.g. a 1nce SIM with ubirch functionality enabled).

**If you have already received pre-programmed testkit hardware from UBIRCH, you can directly head over to [the TestKit manual](TestKit.md) and follow the Quick Start for rapid UBIRCHING.**

If you want to setup your own testkit hardware, read on.

## Setting up your own testkit hardware
### Required hardware
Please acquire the following hardware:

From 1NCE:
- 1NCE SIM Card with SIGNiT/UBIRCH application

From an electronics distributor of your choice:
- [Pycom GPy](https://docs.pycom.io/datasheets/development/gpy/)
- [Pycom Pysense](https://docs.pycom.io/datasheets/boards/pysense/)
- [Pycom LTE-M antenna](https://pycom.io/product/lte-m-antenna-kit/)
- micro SD card
- micro USB cable
 
### Update GPy/Pysense Firmware
Before you start, you should follow these instructions to update your pycom boards:
1. [Update the Pysense firmware](https://docs.pycom.io/updatefirmware/expansionboard/)
    - Please follow the instructions on the linked site.
2. [Assemble the Pysense and GPy](https://docs.pycom.io/gettingstarted/connection/gpy/) 
    - Please refer to the Pysense/Pytrack/Pyscan tab on the linked page for the correct assembly. The RGB LED of the GPy should be on the same side as the Pysense's micro USB connector when you're done.
    - **Also, do not forget to connect the antenna, the GPy might be damaged otherwise.** The antenna is connected to the port next to the RGB LED and reset button on the GPy.    
3. [Update the GPy firmware](https://docs.pycom.io/gettingstarted/installation/firmwaretool/)
    - Please download the firmware update tool from the linked webpage and follow the tool's on-screen instructions
    - Please choose the following settings:
        - port: the serial port where your GPy board is connected
        - high speed transfer: yes/&#9745;
        - advanced settings: no/&#9744;
        - flash from local file: no/&#9744;
        - type: pybytes
        - force update pybytes registration: no/&#9744;
        - enable pybytes: no/&#9744;
        - if asked for the board type, select 'GPy'

You can now proceed to set up your enviroment so you can upload code to the GPy and access it using the 'Pymakr' console.
 
### Set up Environment
Get Pymakr for *Atom* or *Visual Studio Code*:
1. Download and install [**Atom**](https://atom.io) or [**Visual Studio Code**](https://code.visualstudio.com/download) 
2. Install the Pymakr plugin [for Atom](https://docs.pycom.io/pymakr/installation/atom/) or [for VSCode](https://docs.pycom.io/pymakr/installation/vscode/).

You should now have a Pymakr terminal at the bottom of your IDE with buttons to upload and run code. Please do not upload any code yet, as it might interfere with the modem firmware update.

### Update the Modem Firmware
Please do not skip the modem firmware update to **switch the GPy from CAT-M1 to the NB-IoT version**. Without this, there will be no connectivity with the SIM card.

Please perform an upgrade of the modem firmware as shown in [this tutorial video](https://www.youtube.com/watch?v=jNbYhNHzma0). The main steps are oulined below.

1. Acquire the modem firmware files from the Pycom website
    1. Acquire the firmware password: In order to download the password-protected firmware files, register on [forum.pycom.io](http://forum.pycom.io). Then you can find the password in the thread "Announcements & News –> Announcements for members only –> the Firmware Files for the Sequans LTE modem are now secured"
    2. Download the latest modem firmware from [here](https://software.pycom.io/downloads/sequans.html). **Please make sure you'll get the NB-IoT firmware for the modem!**
2. Extract/copy the .dup and .elf files from the zip file onto an SD card, and insert the SD card into the pysense. The files should be placed in the root folder.
3. Connect to your Pymakr console. You might have to click the 'Pymakr Console' button to toggle the board connection, it should show a checkmark and you should see ```>>>``` in the Pymakr terminal. **If you do not see ```>>>``` but other messages (or nothing), there might be code running on the GPy which will possibly interfere with the update.** If you accidentially already uploaded code, please upload an empty main.py to fix this. Altenatively, you can simply add an illegal statement such as "thiswillcauseanerror" to the first line of the main.py and reupload it. This will cause the main.py to exit immediately. Make sure to save the file before uploading.
4. Execute the firmware update by running the commands detailed in the tutorial video in the Pymakr console. If you can't find a matching upgdiff_XXXXX-to-YYYYY.dup for your current firmware version in the zip file, please use the NB1-YYYYY.dup and updater.elf file for the upgrade (e.g. ```sqnsupgrade.run('/sd/NB1-YYYYY.dup','/sd/updater.elf')```). If you run into problems, please **disconnect (for 10 seconds) and reconnect** the board from all power sources before retrying to trigger a reset of the modem. If this does not help, try using a different SD card, a different/shorter USB cable or different USB port with sufficient power.

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
5. **Disconnect (for 10 seconds) and reconnect** the board from all power sources to trigger a reset of the modem.
6. Reset the modem settings to default via the Pymakr console. This will take about 30 seconds and finish with a board reset.
    ```
    >>> from network import LTE
    >>> lte = LTE()
    >>> lte.factory_reset()
    ets Jun  8 2016 00:22:57
    rst:0x7 (TG0WDT_SYS_RESET),boot:0x17 (SPI_FAST_FLASH_BOOT)
    configsip: 0, SPIWP:0xee
    clk_drv:0x00,q_drv:0x00,d_drv:0x00,cs0_drv:0x00,hd_drv:0x00,wp_drv:0x00
    mode:DIO, clock div:1
    load:0x3fff8020,len:8
    load:0x3fff8028,len:2140
    ho 0 tail 12 room 4
    load:0x4009fa00,len:19760
    entry 0x400a05bc
    Pycom MicroPython 1.20.2.rc10 [v1.11-a159dee] on 2020-06-26; GPy with ESP32
    Type "help()" for more information
    ```

For additional help, you can also refer to pycom's [wiki](https://docs.pycom.io/tutorials/lte/firmware/) 

### Insert the SIM
1. Unplug all power sources to the GPy/Pysense board
1. Remove the GPy from the Pysense board
1. Insert SIM card to the underside of the GPy. Make sure the SIM's golden contacts face the GPy board and the cut-off corner goes into the slot first.
1. Re-mount the GPy on the expansion board (pysense or pytrack). The LED on the GPy goes over the micro USB port on the expansion board.
1. Make sure the cellular antenna is still attached to the Gpy next to the RGB LED and reset button.
    > Using LTE/NB-IoT connectivity without the antenna being attached could damage your device!
    
### Get the Testkit Code and flash it to the GPy
It is now time to get the Testkit code and load it into your IDE:
1. Clone this repository in a directory of your choice or download and extract a [release zip file](https://github.com/ubirch/ubirch-testkit/releases).
      ```
      $ git clone https://github.com/ubirch/ubirch-testkit.git
      ```

1. Add the project directory to your IDE's working directory:
    - Atom: `File` -> `Add Project Folder`
    - VS Code: `File` -> `Open Folder`

You should now see the testkit code files (.py) in your IDE's folder view. We can now upload the code to the board:
1. Connect your assembled Pycom device with the inserted SIM card to your computer via USB. Make sure that the Pymakr console is connected. (Checkmark on the "Pymakr Console" Button.) If not, click the "Pymakr Console" button to establish a connection. In the Pymakr console in your IDE, you should see the following output:
      ```
      Connecting to /dev/ttyACM0...
      
      >>> 
      ```
1.  Press the Pymakr `UPLOAD` button. This transfers the example code into the GPy's internal flash.The code will be uploaded to the board and should start to print information in the Pymakr console while it is running. You can ignore error messages regarding missing configuration or auth tokens, as we will set this up later. You now have a GPy running the Testkit code, the next step is to register your SIM with the UBIRCH backend and upload the configuration to the Testkit.

### Set up SIM card and configure the Testkit
1. In order to activate your SIM card in the UBIRCH backend, you'll need to *claim* it by registering the **IMSI**, 
a 15 digit number, at the [UBIRCH web UI](https://console.prod.ubirch.com). If you already know the IMSI of your SIM 
card, you can skip to the next step. 

    If the IMSI is unknown:
    - Make sure you have already uploaded the code to the GPy in the previous step and can see the output in the Pymakr console.
    - Wait for the IMSI to be printed to the console. You can ignore error messages regarding the missing configuration, as we will set this up later.
    - Copy the IMSI
    
    Example output:
    ```
    ++ getting IMSI
    IMSI: 123456789012345
    ++ loading config
            ERROR loading configuration
    Traceback (most recent call last):
      File "main.py", line 85, in <module>
      File "/flash/lib/config.py", line 59, in load_config
    Exception: missing auth token
    Traceback (most recent call last):
      File "main.py", line 282, in <module>    

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
    
1. Configure your device
    * Create a file `config.json` in the `src` directory of the project and paste the `apiConfig` into it.
    * Your config file should then look similar to this one:
        ```json
        {
          "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx",
          "keyService": "https://key.prod.ubirch.com/api/keyService/v1/pubkey/mpack",
          "niomon": "https://niomon.prod.ubirch.com/",
          "data": "https://data.prod.ubirch.com/v1/msgPack",
        }
        ```
        >* If you use a sensor board other than the 'pysense' (which is the default), e.g. a 'pytrack' board, you can add the line `"board": "pytrack",` between the `"data": ...` line and `}`. 
        >* Per default the device will try to establish a `NB-IoT` (LTE) connection. The default APN is `"iot.1nce.net"`.
        >* For more configuration options, see [the TestKit manual](TestKit.md).

1. Upload the program to your device again to transfer the `config.json` to the internal flash of the GPy.
    - Connect the board to USB if you haven't already and watch the Pymakr console in your IDE. It will print the messages from the testkit code running, possibly giving errors about the incorrect configuration. Press `CTRL-C` to stop any running code. If it worked, you should see the following output:
      ```           
      >>> 
      ```
    - Press the Pymakr `UPLOAD` button to upload the updated `config.json` which you created in the project's `src` folder.

You should now see the properly configured Testkit code running in the pymakr console and the boards LED cycle through different colors.

Example output:
```
ets Jun  8 2016 00:22:57

rst:0x1 (POWERON_RESET),boot:0x17 (SPI_FAST_FLASH_BOOT)
configsip: 0, SPIWP:0xee
clk_drv:0x00,q_drv:0x00,d_drv:0x00,cs0_drv:0x00,hd_drv:0x00,wp_drv:0x00
mode:DIO, clock div:1
load:0x3fff8020,len:8
load:0x3fff8028,len:2140
ho 0 tail 12 room 4
load:0x4009fa00,len:19760
entry 0x400a05bc
*** UBIRCH SIM Testkit ***
[some lines omitted]
++ loading config
        no PIN found for 123456789012345
        attaching to the NB-IoT network
                attached: 0 s
        connecting to the NB-IoT network.
                connected: 1 s
        bootstrapping SIM identity 123456789012345
        disconnecting
++ initializing ubirch SIM protocol
UUID: 12345678-1234-1234-1234-00000fbeafea
        connecting to the NB-IoT network
                connected: 0 s
** submitting CSR to identity service ...
++ checking board time
        time is:  (1970, 1, 1, 0, 1, 12, 99628, None)
        time invalid, syncing
        waiting for time sync
        disconnecting
++ getting measurements
        data message [json]: {"data":{"AccPitch":"-19.60","AccRoll":"-7.10","AccX":"0.12","AccY":"0.34","AccZ":"0.96","H":"47.09","L_blue":14,"L_red":15,"P":"95842.49","T":"23.88","V":"4.70"},"msg_type":1,"timestamp":1595449261,"uuid":"05122541-1321-4020-9225-00000fb9a5d4"}
++ creating UPP
        UPP: 9623c41005122542132140209225000013adf293c440590b27d80148bd997039c50683376487ecae4792e92a9f453c67671e2337f1fb8f884919477cc210a02217182d9b505ee2ffc498ce25aaa9f258dcf7e7e0fed900c420631fccd6fc72fd1adda5810d420fdd1e3e0816120c3cf4b85bb0986a97e3ba06c440e7ae1724014854061e2454dae38950eb1334eef887e8004deab224b9994dd5b05265e1dac34d9719adde97f12ce786dad5d54ee2e0e9719656e5ce1507f56158

        data message hash: Yx/M1vxy/RrdpYENQg/dHj4IFhIMPPS4W7CYapfjugY=

++ checking/establishing connection
        connecting to the NB-IoT network
                connected: 0 s
++ sending data
        sending...
++ sending UPP
        sending...
++ waiting for time sync
        time synced
++ preparing hardware for deepsleep
        close connection
        deinit SIM
        deinit LTE
>> going into deepsleep for 17 seconds
[board powers down for 17 seconds and then reboots]
ets Jun  8 2016 00:22:57
rst:0x5 (DEEPSLEEP_RESET),boot:0x17 (SPI_FAST_FLASH_BOOT)
configsip: 0, SPIWP:0xee
clk_drv:0x00,q_drv:0x00,d_drv:0x00,cs0_drv:0x00,hd_drv:0x00,wp_drv:0x00
mode:DIO, clock div:1
load:0x3fff8020,len:8
load:0x3fff8028,len:2140
ho 0 tail 12 room 4
load:0x4009fa00,len:19760
entry 0x400a05bc
*** UBIRCH SIM Testkit ***
[testkit continues as before]
```
You can now head over to [the TestKit manual](TestKit.md) to learn how to use your testkit.

### Support
Please feel free to contact [our helpdesk](https://ubirch.atlassian.net/servicedesk/customer/portal/1) for support.
