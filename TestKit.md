# ubirch TestKit

### Components
- 1NCE SIM Card with SIGNiT application
- Pycom GPy
- Pycom Pysense
- Pycom LTE antenna
- micro SD card
- micro USB cable

### What you need
- micro SD card writer

### Getting started
1. Register at the [ubirch web UI](https://console.prod.ubirch.com) and log in.
 (TODO: bootstrapping currently only deployed on dev stage -> go to https://console.dev.ubirch.com  for now)
1. Go to `Things` and click on `+ ADD NEW DEVICE`. Enter the IMSI of your SIM card to the `ID` field
 and click on `register`. (TODO: not implemented yet)
1. Click on the newly registered "Thing" (your IMSI) and copy the `apiConfig`.
1. Create a file `config.txt` on the SD card and paste the configuration into it. It should look like this:
    ```json
    {
      "password": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx",
      "keyService": "https://key.prod.ubirch.com/api/keyService/v1/pubkey/mpack",
      "niomon": "https://niomon.prod.ubirch.com/",
      "data": "https://data.prod.ubirch.com/v1/msgPack"
    }
    ```
1. Insert the SD card into the Pysense (TODO: picture of TestKit with arrow where to put SD card),
 make sure the antenna is attached to the Gpy and power up the TestKit with the micro USB cable.
  (TODO: more arrows where to put antenna and USB cable)
 
The LED on the GPy flashes in blue colour during the initialization process.
 If anything goes wrong, the LED will change colour:

| colour | meaning | what to do |
|--------|---------|------------|
| yellow | couldn't get config from SD card | Make sure the SD card is inserted correctly and has a file named `config.txt`. The content of the file should look like the example in step 4 including the braces (curly brackets).
| purple | couldn't connect to network (resets automatically) | Try to find a place with better signal. (TODO: is that a good advise?)
| red | couldn't acquire PIN to unlock SIM from ubirch backend or other backend related issue | Make sure you have registered the correct IMSI at the [ubirch web UI](https://console.prod.ubirch.com) and you copied the `apiConfig` for your IMSI to the `config.txt` file.
| green | it's all good. device is measuring, sending data, sealing and sending data certificate to the ubirch backend| see next chapter |
| orange | sending data or data certificate to the ubirch backend failed |  |
| off | sleeping until the next measurement interval (60 seconds) | 

### See the data
1. Go to the [data service dashboard](https://dashboard.prod.ubirch.com/d/qfa7xZhWz/simple-data-service)
1. Login with your Ubirch Web UI account
1. See the data coming in from your device

### Verify the hash
TODO
