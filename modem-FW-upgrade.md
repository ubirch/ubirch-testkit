## Modem Firmware Upgrade

The GPy modem usually comes with a firmware that lets you connect to the CAT-M1 network. In order to connect to the
NB-IoT network, you can switch the GPy Modem Firmware from CAT-M1 to the NB-IoT version. (-> more
info [here](https://docs.pycom.io/updatefirmware/ltemodem/))

> If there is already code uploaded on your Gpy, please upload an empty `main.py`, as it might interfere with the modem firmware upgrade.

Please perform an upgrade of the modem firmware as shown
in [this tutorial video](https://www.youtube.com/watch?v=jNbYhNHzma0). The main steps are outlined below.

1. Acquire the modem firmware files from the Pycom website
    1. Acquire the firmware password: In order to download the password-protected firmware files, register on
       [forum.pycom.io](http://forum.pycom.io). Then you can find the password in the thread "Announcements & News –>
       Announcements for members only –> the Firmware Files for the Sequans LTE modem are now secured"
    2. Download the latest modem firmware from [here](https://software.pycom.io/downloads/sequans.html). **Please make
       sure you'll get the NB-IoT firmware for the modem!**
2. Extract/copy the .dup and .elf files from the zip file onto an SD card, and insert the SD card into the pysense. The
   files should be placed in the root folder.
3. Connect to your Pymakr console. You might have to click the 'Pymakr Console' button to toggle the board connection,
   it should show a checkmark and you should see ```>>>``` in the Pymakr terminal. **If you do not see ```>>>``` but
   other messages (or nothing), there might be code running on the GPy which will possibly interfere with the upgrade.**
   If you accidentally already uploaded code, please upload an empty main.py to fix this. Alternatively, you can simply
   add an illegal statement such as "thiswillcauseanerror" to the first line of the main.py and reupload it. This will
   cause the main.py to exit immediately. Make sure to save the file before uploading.
4. Execute the firmware upgrade by running the commands detailed in the tutorial video in the Pymakr console. If you
   can't find a matching upgdiff_XXXXX-to-YYYYY.dup for your current firmware version in the zip file, please use the
   NB1-YYYYY.dup and updater.elf file for the upgrade (
   e.g. ```sqnsupgrade.run('/sd/NB1-YYYYY.dup','/sd/updater.elf')```). If you run into problems, please **disconnect (
   for 10 seconds) and reconnect** the board from all power sources before retrying to trigger a reset of the modem. If
   this does not help, try using a different SD card, a different/shorter USB cable or different USB port with
   sufficient power.

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
6. Reset the modem settings to default via the Pymakr console. This will take about 30 seconds and finish with a board
   reset.
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