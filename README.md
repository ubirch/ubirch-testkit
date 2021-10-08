# UBIRCH Testkit

A micropython client for the UBIRCH protocol on a SIM

The ubirch testkit is a combination of hardware based on pycom hardware modules (we use GPy and Pysense) and micropython
example code to demonstrate the usage of the UBIRCH protocol. It allows for easy use and evaluation of the 'blockchain
on a SIM' application which implements UBIRCH functionality inside a SIM card. The SIM card needs to have the '
SIGNiT' applet for cryptographic functionality (e.g. a 1nce SIM with ubirch functionality enabled).

**If you have already received pre-programmed testkit hardware from UBIRCH, you can directly head over
to [the TestKit manual](TestKit.md) and follow the Quick Start for rapid UBIRCHING.**

If you want to setup your own testkit hardware, read on.

---
**INFO**

This firmware supports pysense and pytrack hardware **version 2.x**. If you have a pysense or pytrack v1.x, you can check
out the branch [pysense-v1](https://github.com/ubirch/ubirch-testkit/tree/pysense-v1), but note that this
version might not be maintained anymore.

 ---

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
    - Please refer to the Pysense/Pytrack/Pyscan tab on the linked page for the correct assembly. The RGB LED of the GPy
      should be on the same side as the Pysense's micro USB connector when you're done.
    - **Also, do not forget to connect the antenna, the GPy might be damaged otherwise.** The antenna is connected to
      the port next to the RGB LED and reset button on the GPy.
3. [Update the GPy firmware](https://docs.pycom.io/updatefirmware/device/)
      - Please download the firmware update tool from the linked webpage and follow the tool's on-screen instructions
      - Please choose the following settings:
         - port: the serial port where your GPy board is connected
         - high speed transfer: yes/&#9745;
         - advanced settings: yes/&#9745;
         - flash from local file: no/&#9744;
         - type: pybytes
         - force update Pybytes registration: no/&#9744;
         - enable Pybytes/SmartConfig support: no/&#9744;
         - Advanced Settings:
           - Information: `Device Type:` `GPy`
           - Type / Version: `pybytes` **`1.20.2.r4`**
4. [Update modem firmware](https://docs.pycom.io/updatefirmware/ltemodem/)
    - Please follow the instructions on the linked site.

You can now proceed to set up your environment, so you can upload code to the GPy and access it using the 'Pymakr'
console.

### Set up Environment

Get Pymakr for *Atom* or *Visual Studio Code*:

1. Download and install [**Atom**](https://atom.io) or [**Visual Studio Code**](https://code.visualstudio.com/download)
2. Install the Pymakr plugin [for Atom](https://docs.pycom.io/pymakr/installation/atom/)
   or [for VSCode](https://docs.pycom.io/pymakr/installation/vscode/).

You should now have a Pymakr terminal at the bottom of your IDE with buttons to upload and run code.

### Insert the SIM

1. Unplug all power sources to the GPy/Pysense board
1. Remove the GPy from the Pysense board
1. Insert SIM card to the underside of the GPy. Make sure the SIM's golden contacts face the GPy board and the cut-off
   corner goes into the slot first.
1. Re-mount the GPy on the expansion board (pysense or pytrack). The LED on the GPy goes over the micro USB port on the
   expansion board.
1. Make sure the cellular antenna is still attached to the Gpy next to the RGB LED and reset button.
   > Using LTE/NB-IoT connectivity without the antenna being attached could damage your device!

### Get the Testkit Code and flash it to the GPy

It is now time to get the Testkit code and load it into your IDE:

1. Clone this repository in a directory of your choice or download and extract
   a [release zip file](https://github.com/ubirch/ubirch-testkit/releases).
      $ 
      ```git clone https://github.com/ubirch/ubirch-testkit.git
      ```
1. ```sudo usermod -a -G dialout $USER
```
1. Add the project directory to your IDE's working directory:
    - Atom: `File` -> `Add Project Folder`
    - VS Code: `File` -> `Open Folder`

You should now see the testkit code files (.py) in your IDE's folder view. We can now upload the code to the board:

1. Connect your assembled Pycom device with the inserted SIM card to your computer via USB. Make sure that the Pymakr
   console is connected. (Checkmark on the "Pymakr Console" Button.) If not, click the "Pymakr Console" button to
   establish a connection. In the Pymakr console in your IDE, you should see the following output:
      ```
      Connecting to /dev/ttyACM0...
      
      >>> 
      ```
1. Press the Pymakr `UPLOAD` button. This transfers the example code into the GPy's internal flash.The code will be
   uploaded to the board and should start to print information in the Pymakr console while it is running. You can ignore
   error messages regarding missing configuration or auth tokens, as we will set this up later. You now have a GPy
   running the Testkit code, the next step is to register your SIM with the UBIRCH backend and upload the configuration
   to the Testkit.

### Set up SIM card and configure the Testkit

1. In order to activate your SIM card in the UBIRCH backend, you'll need to *claim* it by registering the **IMSI**, a 15
   digit number, at the [UBIRCH web UI](https://console.prod.ubirch.com). If you already know the IMSI of your SIM card,
   you can skip to the next step.

   If the IMSI is unknown:
    - Make sure you have already uploaded the code to the GPy in the previous step and can see the output in the Pymakr
      console.
    - Wait for the IMSI to be printed to the console. You can ignore error messages regarding the missing configuration,
      as we will set this up later.
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
        - Enter the **tag** matching your sensor board, usually `pysense`. Please **make sure you enter the tag
          correctly as otherwise there will be no display of the sensor data** in the console.
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
          "data": "https://data.prod.ubirch.com/v1/msgPack"
        }
        ```
      > * If you use a sensor board other than the 'pysense' (which is the default), e.g. a 'pytrack' board, you can add the line `"board": "pytrack",` between the `"data": ...` line and `}`.
      >* Per default the device will try to establish a `NB-IoT` (LTE) connection. The default APN is `"iot.1nce.net"`.
      >* For more configuration options, see [the TestKit manual](TestKit.md).

1. Upload the program to your device again to transfer the `config.json` to the internal flash of the GPy.
    - Connect the board to USB if you haven't already and watch the Pymakr console in your IDE. It will print the
      messages from the testkit code running, possibly giving errors about the incorrect configuration. Press `CTRL-C`
      to stop any running code. If it worked, you should see the following output:
      ```           
      >>> 
      ```
    - Press the Pymakr `UPLOAD` button to upload the updated `config.json` which you created in the project's `src`
      folder.

You should now see the properly configured Testkit code running in the pymakr console and the boards LED cycle through
different colors.

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
