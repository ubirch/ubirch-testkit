1. Download Atom Editor ([download](https://github.com/atom/atom/releases))
    * Version 1.37.0 or lower
    * Windows: AtomSetup-x64.exe
    * Linux: atom-amd64.deb
1. Install Atom Editor
    * Windows: run setup
    * Linux: 
      ```bash
      sudo dpkg -i atom-amd64.deb
      sudo apt install -f
      ```
1. Start Atom Editor
1. Connect Device via USB
    * watch console window in Atom to see it worked
1. Download Pycom Upgrader ([download](https://pycom.io/downloads/))
1. Download UBIRCH Pycom Firmware ([download](https://github.com/ubirch/example-micropython/releases))
    * select the correct firmware for your device (WiPy, Lopy4, GPy, ...)
1. CLOSE ATOM or DISCONNECT DEVICE
1. Run Pycom Upgrader and Flash Firmware
    * select flash from file and use downloaded file from step 6.
1. Start Atom Editor or CONNECT DEVICE
1. Download example firmware
    * Menu View -> Toggle Command Palette
    * Enter `git clone` and press return
    * Paste `https://github.com/ubirch/example-micropython` and clone it
1. Create a file `boot.json` in the `src` directory
    ```json
    {
      "networks": {
        "<NETWORK NAME>": "<PASSWORD FOR NETWORK>"
      },
      "timeout": 5000,
      "retries": 10
    }
    ``` 
1. Create a file `settings.json` in the `src` directory
    ```json
    {
        "type": "pysense",
        "bootstrap": {
            "authorization": "Basic <ASK>",
            "tenant": "ubirch",
            "host": "management.cumulocity.com"
        },
        "interval": 60
    }
    ```
 1. Press `UPLOAD` just above the console window in Atom
 1. Wait for all files to upload until you see a `UUID : XXXX` output, copy the UUID!
 1. Visit [https://ubirch.cumulocity.com](https://ubirch.cumulocity.com)
 1. Login with the credentials you have created after your invitation mail!
 1. Select the nine-dots menu (top right) and select `Device Management`
 1. Click on menu `Devices` (left) and click on `Registration`
 1. Click on `Register Device` and manually add your device entering the UUID copied in step 14
    * **also select Pycom as group**
 1. Reset the pycom device (button next to RGB LED)
 1. Wait in Cumulocity for your device until an `Accept` button appears!
 1. Click `Accept`
 1. Select nine-dots menu (top right) and select `Cockpit`
 1. Select Groups (left) and click `Pycom` group
 1. Find your device (check last 4 characters from UUID)
 1. Select `Data Explorer` and add Data points in right panel
 
 ENJOY!