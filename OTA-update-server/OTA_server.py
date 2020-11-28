#!/usr/bin/env python
#
# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#

# Firmware over the air update server
#
# Version History
#  1.0   - Initial release (Sebastian Goscik)
#  1.0.1 - Extended by ubirch GmbH in Sept. 2020
#
# Setup
# -------
# This script runs a HTTP server on port 62633 that provisions over the air
# (OTA) update manifests in JSON format as well as serving the update content.
# The manifests are signed by the server and the signature is checked by the device.
# This script should be run in a directory that contains every version of the
# end devices code, in the following structure:
#
#  - server directory
#    |- this_script.py
#    |- 1.0.0
#    |  |- flash
#    |  |   |- lib
#    |  |   |  |- lib_a.py
#    |  |   |- main.py
#    |  |- sd
#    |     |- some_asset.txt
#    |     |- asset_that_will_be_removed.wav
#    |- 1.0.1
#    |  |- flash
#    |  |   |- lib
#    |  |   |  |- lib_a.py
#    |  |   |  |- new_lib.py
#    |  |   |- main.py
#    |  |- sd
#    |     |- some_asset.txt
#    |- firmware_1.0.0.bin
#    |- firmware_1.0.1.bin
#
# The top level directory that contains this script can contain one of two
# things:
#     Update directory: These should be named with a version number compatible
#                       with the python LooseVersion versioning scheme
#                      (http://epydoc.sourceforge.net/stdlib/distutils.version.LooseVersion-class.html).
#                      They should contain the entire file system of the end
#                      device for the corresponding version number.
#    Firmware: ***This feature is currently disabled.***
#              These files should be named in the format "firmare_VERSION.bin",
#              where VERSION is a a version number compatible with the python
#              LooseVersion versioning scheme
#              (http://epydoc.sourceforge.net/stdlib/distutils.version.LooseVersion-class.html).
#              This file should be in the format of the appimg.bin created by
#              the pycom firmware build scripts.
#
# How to use
# -----------
# To use the server, please prepare these steps:
#  -Set up the directory structure outlined above.
#    - Tip for testing: create two folders "OTA-update-server/1.0.0/flash"
#      and "OTA-update-server/1.0.1/flash". Then simply copy the contents of the "src" folder into
#      both folders and add some extra files or do modifications to the "1.0.1/flash" folder. Don't
#      forget to upload the 1.0.0 code also to the device.
#  - Generate a key pair (RSA 4096 bit):
#    - For the private key, first generate a key pair, and then export the private key into the corresponding enviroment variable:
#       - generate a keypair using e.g. openssl:
#           cd OTA-update-server
#           openssl genrsa -out OTA_signing_key_rsa_4096.pem 4096
#       - pipe the key file into the terminal enviroment variable before starting the server, e.g.:
#           export OTA_SERVER_SIGNING_KEY_RSA_4096=`cat ./OTA_signing_key_rsa_4096.pem`
#    - Put the public key modulus in boot.py OTA class (`PUB_MOD_RSA_4096 = "ab01...ef"`):
#       - export the public verifying key and afterwards display the modulus using e.g. openssl:
#           openssl rsa -in OTA_signing_key_rsa_4096.pem -outform PEM -pubout -out OTA_verifying_key_rsa_4096.pem
#           openssl rsa -pubin -modulus -noout -in OTA_verifying_key_rsa_4096.pem
#        -copy the pubkey modulus hex output of the second command to boot.py after the "PUB_MOD_RSA_4096 =" in the OTA class
#  - Set the server URL and check the other settings in boot.py in check_OTA_update()
#  - If using wifi instead of NB-IoT: Set WiFi secrets in ota_wifi_secrets.py (see ota_wifi_secrets.py.example.txt), and in
#    check_OTA_update() comment the NBIoTOTA setup section out and the WifiOTA section in.
#
# After setting up the above steps, start the server by simply running the `OTA_server.py` script using python 3:
# python3 OTA_server.py
# This will run a HTTP server on port 62633 (this can be changed in the code if necessary).
# Power-on/hard-reset the pycom board to trigger execution of boot.py. The board will establish a connection and
# request an update manifest from the server and if necessary update itself to the latest version.
# The OTA procedure is triggered on every reset unless the device was simply
# sleeping (deepsleep reset). The OTA device code is run from boot.py
#
# Implementation Details
#-----------------------
#
# The server will serve all the files in the directory as expected along with one
# additional special file, "manifest.json". This file does not exist on the
# file system but is instead generated when requested and contains the required
# change to bring the end device from its current version to the latest
# available version. You can see an example of this by pointing your web
# browser at:
#    http://127.0.0.1:62633/manifest.json?current_ver=1.0.1
# The `current_ver` field at the end of the URL should be set to the current
# firmware version of the end device. The generated file is not strictly a json file
# as it contains three sections marked by headers: the manifest json ("MANIFEST[len(data)]:"),
# the signature type ("SIGNATURE_TYPE[len(data)]:"), and the signature itself ("SIGNATURE_DATA[len(data)]:").
# The manifest data section is in json format. The signature is carried out over the string of the manifest json data.
# The generated manifest json will contain lists of which files are new, have changed
# or need to be deleted along with SHA512 hashes of the files. Below is an example
# of what such a manifest might look like:

# MANIFEST[754]:{
#     "delete": [
#         "flash/removed_file.txt"
#     ],
#     "new": [
#         {
#             "URL": "http://127.0.0.1:62633/1.0.3/flash/new_file.txt",
#             "dst_path": "/flash/new_file.txt",
#             "hash": "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"
#         },
#         {
#             "URL": "http://127.0.0.1:62633/1.0.3/flash/new_file2.txt",
#             "dst_path": "/flash/new_file2.txt",
#             "hash": "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"
#         }
#     ],
#     "new_version": "1.0.3",
#     "old_version": "1.0.1",
#     "request_id": null,
#     "update": []
# }SIGNATURE_TYPE[27]:SIG02_PKCS1_PSS_4096_SHA512SIGNATURE_DATA[1024]:84...de
#
#
# The manifest json data contains the following fields:
#  "delete": A list of paths to files which are no longer needed
#  "firmware": The URL and SHA512 hash of the firmware image for the board itself.
#  "new": the URL, path on end device and SHA512 hash of all new files
#  "update": the URL, path on end device and SHA512 hash of all files which
#            existed before but have changed.
#  "new_version": The version number that this manifest will update the client to
#  "old_version": The version that the manifest compares the changes to/is based on.
#                 If the returned version does not match the device version, the device aborts the update.
#  "request_id": The request ID send by the device in the query string. This is used to prevent
#                replay attacks. The device will generate a random ID for each request and check if
#                the generated manifest contains the same ID. See OTA class in boot.py for details.
#
# Note: The version number of the files might not be the same as the firmware.
#       The highest available version number, higher than the current client
#       version is used for both firmware and files. This may differ between
#       the two.
#
# Note: In the standard setting, the OTA bootloader (boot.py and related files) are protected by the server
#       and never included in update manifests. This can be changed with the PROTECT_BOOTLOADER variable. Use with 
#       caution.
#      
# In order for the URL's to be properly formatted you are required to send a
# "host" header along with your HTTP get request e.g:
# GET /manifest.json?current_ver=1.0.0 HTTP/1.0\r\nHost: 192.168.1.144:62633\r\n\r\n

import os
import socket
import json
import hashlib
import filecmp
import re
from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA256,SHA512
from Crypto.PublicKey import RSA

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from distutils.version import LooseVersion

PORT = 62633
PROTECT_BOOTLOADER = True #if this is true, the server will never add protected files to the update manifest
OTA_SERVER_SIGNING_KEY_RSA_4096 = os.getenv('OTA_SERVER_SIGNING_KEY_RSA_4096') #expects the signing key in pem format, e.g. via export OTA_SERVER_SIGNING_KEY_RSA_4096=`cat ./OTA_signing_key_rsa_4096.pem`


class OTAHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        print("Got query for: {}".format(repr(self.path)))

        # Parse the URL
        path = urlparse(self.path).path
        query_components = parse_qs(urlparse(self.path).query)
        host = self.headers.get('Host')

        # Generate update manifest
        if path == "/manifest.json":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            # If query specified a version generate a diff from that version
            # otherwise return a manifest of all files
            if "current_ver" in query_components:
                current_ver = query_components["current_ver"][0]
            else:
                # This assumes there is no version lower than 0
                current_ver = '0'

            # If query specified a request id, return it in the signed
            # manifest (prevents replay/version pinning attacks)
            if "reqid" in query_components:
                request_id = query_components["reqid"][0]
            else:                
                request_id = None

            # Send signed manifest data
            # First create a JSON string of the manifest, then sign the data
            # of that string which results in a signature data string (not JSON in this case).
            # Finally, assemble both strings and send them. Signature and manifest data are distinguished
            # using headers indicating their size (for easy and unambigous dissassembly at the client).
            print("Generating a manifest from version: {}".format(current_ver))
            manifest = generate_manifest(current_ver, host, request_id)
            manifest_string = json.dumps(manifest,
                           sort_keys=True,
                           indent=4,
                           separators=(',', ': '))            

            # get signature string for manifest JSON string 
            # (signature string will already include headers)
            signature_string = get_manifest_signature(manifest_string)

            #add header to manifest JSON string
            manifest_string = "MANIFEST[{}]:{}".format(len(manifest_string), manifest_string)

            manifest_and_sig = manifest_string + signature_string
            
            #print(manifest_and_sig)
            
            self.wfile.write(manifest_and_sig.encode())

        # Send file
        else:
            try:
                with open(os.path.join('.', self.path[1:]), 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type',
                                     'application/octet-stream')
                    self.end_headers()
                    self.wfile.write(f.read())
            # File could not be opened, send error
            except IOError as e:
                self.send_error(404, "File Not Found {}".format(self.path))


# Searches the current working directory for the directory named with the
# highest version number as per LooseVersion.
def get_latest_version():
    latest = None
    for d in os.listdir('.'):
        if os.path.isfile(d):
            continue
        if latest is None or LooseVersion(latest) < LooseVersion(d):
            latest = d
    return latest


# Returns a list of all files found relative to `path`.
# Parameters:
#   path - The directory that will be traversed, results will be relative to
#          this path.
#   Ignore - A list of file names which to ignore
def get_all_paths(path, ignore=[]):
    ignore = set(ignore)
    paths = []
    for entry in os.walk(path,followlinks=True):
        d, _, files = entry
        files = set(files).difference(ignore)
        paths += [os.path.join(d, f) for f in files]
    out = [d.replace('{}{}'.format(path, os.path.sep), '') for d in paths]
    return set(out)


# Returns a tuple containing three lists: deleted files, new_file, changed
# files.
# Parameters
#    left - The original directory
#    right - The directory with updates
#    ignore - A list o file name which to ignore
def get_diff_list(left, right, ignore=['.DS_Store', 'pymakr.conf']):
    left_paths = get_all_paths(left, ignore=ignore)
    right_paths = get_all_paths(right, ignore=ignore)
    new_files = right_paths.difference(left_paths)
    to_delete = left_paths.difference(right_paths)
    common = left_paths.intersection(right_paths)

    to_update = []
    for f in common:
        if not filecmp.cmp(os.path.join(left, f),
                           os.path.join(right, f),
                           shallow=False):
            to_update.append(f)
    

    #check if lists contain protected files (e.g. bootloader, bootloader settings, and version)
    #these are protected anywhere (=if a path ends with them)
    if PROTECT_BOOTLOADER:
        protected_files = ["boot.py","OTA_VERSION.py","ota_wifi_secrets.py"]
        lists_to_check = [to_delete, new_files, (to_update)]
        
        for filelist in lists_to_check:#for every list that was generated           
            to_remove = []
            for filepath in filelist:#for every path in that list/set
                for protected_file in protected_files:#for every filename that is protected
                    if os.path.basename(filepath).lower() == protected_file.lower():#check filename (case insensitive)
                        to_remove.append(filepath)#remember this path for removal
                        print("Warning: removing protected file '{}' (on path '{}') from update manifest.".format(protected_file,filepath))
            for item in to_remove:#remove all paths that contain protected files
                try:
                    filelist.remove(item)
                except ValueError: #list does not have item (anymore), e.g. by double match
                    pass
            

    return (to_delete, new_files, (to_update))


# Searches the current working directory for a file starting with "firmware_"
# followed by a version number higher than `current_ver` as per LooseVersion.
# Returns None if such a file does not exist.
# Parameters
#    path - the path to the directory to be searched
#    current_ver - the result must be higher than this version
#
def get_new_firmware(path, current_ver):
    latest = None
    for f in os.listdir(path):
        # Ignore directories
        if not os.path.isfile(f):
            continue

        try:
            m = re.search(r'firmware_([0-9a-zA-Z.]+)(?=.bin|hex)', f)
            version = m.group(1)
            if LooseVersion(current_ver) < LooseVersion(version):
                latest = f
        except AttributeError:
            # file does not match firmware naming scheme
            pass
    return latest


# Returns a dict containing a manifest entry which contains the files
# destination path, download URL and SHA512 hash.
# Parameters
#    path - The relative path to the file
#    version - The version number of the file
#    host - The server address, used in URL formatting
def generate_manifest_entry(host, path, version):
    path = "/".join(path.split(os.path.sep))
    entry = {}
    entry["dst_path"] = "/{}".format(path)
    entry["URL"] = "http://{}/{}/{}".format(host, version, path)
    data = open(os.path.join('.', version, path), 'rb').read()
    hasher = hashlib.sha512(data)
    entry["hash"] = hasher.hexdigest()
    return entry


# Returns the update manivest as a dictionary with the following entries:
#    delete - List of files that are no longer needed
#    new - A list of manifest entries for new files to be downloaded
#    update - A list of manifest entries for files that require Updating
#    version - The version that this manifest will bring the client up to
#    firmware(optional) - A manifest entry for the new firmware, if one is
#                         available.
def generate_manifest(current_ver, host,request_id):
    latest = get_latest_version()

    # If the current version is already the latest, there is nothing to do
    # but we need to return at least manifest with the request ID, else this would generate
    # a signed "do nothing" manifest which can be used for version pinning attacks
    manifest = {            
    "new_version": latest,
    "old_version": current_ver,
    "request_id": request_id
    }
    if latest == current_ver:
        return manifest #if the versions are the same we are done here

    # Get lists of difference between versions
    to_delete, new_files, to_update = get_diff_list(current_ver, latest)

    #add lists to manifest
    manifest.update(
        {
         "delete": list(to_delete),
         "new": [generate_manifest_entry(host, f, latest) for f in new_files],
         "update": [generate_manifest_entry(host, f, latest) for f in to_update]
        }
    )

    # If there is a newer firmware version add it to the manifest
    new_firmware = get_new_firmware('.', current_ver)
    if new_firmware is not None:
        entry = {}
        entry["URL"] = "http://{}/{}".format(host, new_firmware)
        data = open(os.path.join('.', new_firmware), 'rb').read()
        hasher = hashlib.sha512(data)
        entry["hash"] = hasher.hexdigest()
        manifest["firmware"] = entry

    return manifest

def get_manifest_signature(manifest_string: str)-> str:
    """Returns a string for the signature data for a manifest (JSON) string.
    Can actually be used to sign any type of string data. String type is
    mandatory to avoid JSON encoding ambiguities when signing. Signature string will
    have headers (including size) for a "type" identifier and the signature data itself.
    """

    if OTA_SERVER_SIGNING_KEY_RSA_4096 is None:
        raise ValueError("Server signing key not set. Can't create manifest.")

    #calculate signature (SHA256)
    # signature_type = "SIG01_PKCS1_PSS_4096_SHA256"
    # key = RSA.importKey(OTA_SERVER_SIGNING_KEY_RSA_4096)
    # h = SHA256.new()
    # h.update(manifest_string.encode('utf-8'))
    # signer = PKCS1_PSS.new(key)
    # signaturebytes = signer.sign(h)
    # signature_data = signaturebytes.hex()

    #calculate signature (SHA512)
    signature_type = "SIG02_PKCS1_PSS_4096_SHA512"
    key = RSA.importKey(OTA_SERVER_SIGNING_KEY_RSA_4096)
    h = SHA512.new()
    h.update(manifest_string.encode('utf-8'))
    signer = PKCS1_PSS.new(key)
    signaturebytes = signer.sign(h)
    signature_data = signaturebytes.hex()

    #add headers
    signature_type = "SIGNATURE_TYPE[{}]:{}".format(len(signature_type), signature_type)
    signature_data = "SIGNATURE_DATA[{}]:{}".format(len(signature_data), signature_data)

    manifest_signature = signature_type + signature_data
    return manifest_signature


if __name__ == "__main__":

    if OTA_SERVER_SIGNING_KEY_RSA_4096 is None:
            raise ValueError("Server signing key enviroment variable (OTA_SERVER_SIGNING_KEY_RSA_4096) not set. Can't start server.")

    server_address = ('', PORT)
    httpd = HTTPServer(server_address, OTAHandler)
    httpd.serve_forever()
