Overview
--------

This directory contains an example implementation of the over the air (OTA)
firmware update server. The whole funtionality needs two components:
  - A server that serves the update files and generates update "manifests", which is in this folder.
  - A class that allows a Pycom module to perform updates from the server, which resides in boot.py in the src directory.

To run the update server you need to add subfolders with the files for each version.
For a detailed description of how the server expects the directory to be structured
please read the comment at the top of `OTA_server.py`. You will also
need to check the settings in boot.py, and add your wifi settings, if you want to use wifi
(see ota_wifi_secrets.py.example.txt). Furthermore, you need to generate a keypair for signing and add
the private key to the server directory and the public key modulus in boot.py. See `OTA_server.py`
for detailed setup steps.

Setup
-----
Please see "How to use" in `OTA_server.py` for setup steps.
