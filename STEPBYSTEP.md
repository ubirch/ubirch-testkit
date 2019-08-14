## Prepare Local Environment
1. Download Atom Editor ([download](https://github.com/atom/atom/releases))
    * Version 1.37.0 or lower
    * Windows: AtomSetup-x64.exe
    * Linux: atom-amd64.deb
1. Install Atom Editor
    * Windows: run setup exe
    * Linux:
      ```bash
      sudo dpkg -i atom-amd64.deb
      sudo apt install -f
      ```
1. Start Atom Editor
1. Open Install Packages (Menu `File >> Settings >> Install`)
     * Enter `pymakr` in search field
     * Install pymakr package
1. Connect Pycom Device via USB
    * watch pymakr console window in Atom to see if it worked (should show up automatically on the buttom you the Atom window)
1. CLOSE Atom Editor or DISCONNECT the Pycom Device

## Flash Pycom Devices
1. Download Pycom Upgrader ([download](https://pycom.io/downloads/))
1. Download UBIRCH Pycom Firmware ([download](https://github.com/ubirch/example-micropython/releases/tag/pybytes-ed25519))
    * select the correct firmware for your device (WiPy, Lopy4, GPy, ...)
1. Run Pycom Upgrader and Flash Firmware
    * On screen the third screen named `COMMUNICATION`select the right COM port and check the `flash from local file` checkbox
    * select file downloaded in step 8 and continue the process
    * wait till flash process finished successfully

## Configure Pycom Device
1. Re-Start Atom Editor or re-connect device
1. Download example firmware code
    * Click menu `View >> Toggle Command Palette`
    * Enter `git clone` and press return
    * Paste `https://github.com/ubirch/example-micropython` and clone it
    * A new project with the project tree at the right of Atom should open automatically

1. Create a file `boot.json` in the `src` directory in the project tree with the following content
    ```json
    {
      "networks": {
        "<WIFI SSID>": "<WIFI PASSWORD>"
      },
      "timeout": 5000,
      "retries": 10
    }
    ```
    * Replace `<WIFI SSID>` with the name of your wifi network
    * Replace `<WIFI PASSWORD>` with the password to your wifi network
1. Create a file `settings.json` in the `src` directory in the project tree with the following content
    ```json
    {
        "type": "<EXPANSION BOARD>",
        "bootstrap": {
            "authorization": "Basic <ACCESS TOKEN>",
            "tenant": "ubirch",
            "host": "management.cumulocity.com"
        },
        "interval": 60
    }
    ```
    * Replace `<EXPANSION BOARD>` with the type of extension board you are using your with your Pycom, valid values are: `pysense`, `pytrack` and **TODO**
    * Replace `<ACCESS TOKEN>` with the access token you received upfront
1. Press `UPLOAD` just above the pymakr console window in Atom
1. Wait for all files to upload until you see a `UUID : XXXX` output, copy the **UUID**!

## Configure Device in IoT Platform
1. Visit [https://ubirch.cumulocity.com](https://ubirch.cumulocity.com)
1. Login with the credentials you have created after your invitation mail / we provided you
1. Select the nine-dots menu (top right) and select `Device Management`
1. Click on menu `Devices` (left) and click on `Registration`
1. Click on `Register Device` and manually add your device entering the **UUID** copied in the last step of the previous chapter
    * **also select Pycom as group**
1. Reset the pycom device (button next to RGB LED)
1. Wait in Cumulocity for your device until an `Accept` button appears!
1. Click `Accept`
1. Select nine-dots menu (top right) and select `Cockpit`
1. Select Groups (left) and click `Pycom` group
1. Find your device (check last 4 characters from **UUID**)
1. Select `Data Explorer` and add Data points in right panel
1. Enjoy the data coming in from your device

## (Optional - for experts) Check Blockchain Anchoring [DRAFT]
1. While the Pycom is connected and running, and Atom is open, check the pymakr console in Atom and wait for a hash of a measurement certificate to appear, e.g.:
```
sending measurement certificate ...
hash: b’w4DhI6HSrDFsczEEdR1U5w2IPQrzAw9gEocYPpYGfJIdDpeQmEuY/aWY1dqqWUeAHmJGQyGKCD0ctVj6KUlTsA==\n’
```
    * In this example the hash to copy is **w4DhI6HSrDFsczEEdR1U5w2IPQrzAw9gEocYPpYGfJIdDpeQmEuY/aWY1dqqWUeAHmJGQyGKCD0ctVj6KUlTsA==**
1. Send a POST request to the UBIRCH verification service, e.g. by using **curl** (or any other tool to send POST requests):
    ```
    curl -s -X POST -H "accept: application/json" -H "Content-Type: text/plain" -d "$HASH" "$URL"
    ```
    * Replace `$HASH` with the hash copied in step 1
    * Replace `$URL` with
        * https://verify.dev.ubirch.com/api/verify or
        * https://verify.demo.ubirch.com/api/verify or
        * https://verify.prod.ubirch.com/api/verify
        * depending on the environment you are using
1. The response will list all blockchain anchors containing this measurement certificate. The `txid` (Blockchain Transaction ID) of each anchors entry can be used to lookup the entry in the according blockchain explorer (consider the `blockchain` and `network_type` attribute to find the right explorer)
