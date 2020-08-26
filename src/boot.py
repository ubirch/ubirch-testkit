#!/usr/bin/env python
# Based on example OTA code from pycom which from
# https://github.com/pycom/pycom-libraries/tree/master/examples/OTA
# Copyright notice for original example code:
#
# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#

import network
import socket
import machine
import ujson
import uhashlib
import ubinascii
import gc
import pycom
import os
import machine
import time
from time import sleep
import sys

from ota_wifi_secrets import WIFI_SSID, WIFI_PW

# Try to get version number
try:
    from OTA_VERSION import VERSION
except ImportError:
    VERSION = '1.0.0'

# Configuration
SERVER_IP = "10.42.0.1"

# To make the OTA bootloader self-contained, and hopefully more reliable, the library/classes are directly included here instead of an extra lib

class OTA():
    # The following two methods need to be implemented in a subclass for the
    # specific transport mechanism e.g. WiFi

    def connect(self):
        raise NotImplementedError()

    def get_data(self, req, dest_path=None, hash=False):
        raise NotImplementedError()

    # OTA methods

    def get_current_version(self):
        return VERSION

    def check_manifest_signature(self,manifest:str,sig_type:str,sig_data:str)->bool:
        print("Checking signature")
        if sig_type != "dummy_sig_type":
            raise Exception("Unknown signature type: {}".format(sig_type))
        
        if sig_data != "01234deadbeef":
            return False            

        print("Signature OK")
        return True

    def extract_from_response(self,header:str,response:str)->(str,str):
        """Extracts the data from a server response using the header.
        Returns the data itself and the response with data and header removed
        Expected format: HEADER_NAME[len(data)]:data, e.g. MYDATA[3]:123SOMEOTHERDATA[2]:ab etc.
        """
        size_marker_start = "["
        size_marker_end = "]:"

        #find header including the begin of size field
        header_start = response.find(header+size_marker_start)
        if header_start == -1:#no valid header found
            return("",response)

        #determine start position of size integer
        size_start = header_start + len(header) + len(size_marker_start)

        #find end of size field
        size_end = response.find(size_marker_end, size_start)
        if size_end == -1:#end of size field not found
            return("",response)

        #extract size string and try conversion
        size_str = response[size_start:size_end]
        try:
            data_size = int(size_str)
        except:#size string conversion failed
            return("",response)
        
        #extract data string
        data_start = size_end+len(size_marker_end)
        data_end = data_start + data_size
        if data_end > len(response):#data size is larger than available data
            return("",response)            
        data_str = response[data_start:data_end]

        #remove data and header from response
        remaining_response = response[:header_start]+response[data_end:]

        return(data_str,remaining_response)
    
    def get_update_manifest(self):
        """Get the manifest data from server and check signature.
        Gets the data, splits it into the strings for manifest (JSON), signature type, and signature data
        using the headers. Then checks the signature and finally parses the JSON of the manifest.
        """
        req = "manifest.json?current_ver={}".format(self.get_current_version())
        response = self.get_data(req).decode()

        # get the data from the headers and repeat with the remaining response
        # we get/remove the manifest json first as it is the most critical to remove
        # since it's data is arbitrary and might contain 'header-like' strings
        manifest_str,response = self.extract_from_response("MANIFEST",response)
        sig_type_str,response = self.extract_from_response("SIGNATURE_TYPE",response)
        sig_data_str,response = self.extract_from_response("SIGNATURE_DATA",response)

        #check that all data was found
        if len(manifest_str) == 0 or \
            len(sig_type_str) == 0 or \
            len(sig_data_str) == 0 :
            raise Exception("Could not find all required headers in response.")
        
        #check signature
        if self.check_manifest_signature(manifest_str,sig_type_str,sig_data_str):        
            manifest = ujson.loads(manifest_str)
        else:
            raise Exception("Signature of manifest is invalid")                   
        
        gc.collect()        
        return manifest

    def update(self):
        manifest = self.get_update_manifest()
        if manifest is None:
            print("Already on the latest version")
            return

        # Download new files and verify hashes
        for f in manifest['new'] + manifest['update']:
            # Upto 5 retries
            for _ in range(5):
                try:
                    self.get_file(f)
                    break
                except Exception as e:
                    print(e)
                    msg = "Error downloading `{}` retrying..."
                    print(msg.format(f['URL']))
            else:
                raise Exception("Failed to download `{}`".format(f['URL']))

        # Backup old files
        # only once all files have been successfully downloaded
        for f in manifest['update']:
            self.backup_file(f)

        # Rename new files to proper name
        for f in manifest['new'] + manifest['update']:
            new_path = "{}.new".format(f['dst_path'])
            dest_path = "{}".format(f['dst_path'])

            os.rename(new_path, dest_path)

        # `Delete` files no longer required
        # This actually makes a backup of the files incase we need to roll back
        for f in manifest['delete']:
            self.delete_file(f)

        # Flash firmware
        if "firmware" in manifest:
            self.write_firmware(manifest['firmware'])

        # Save version number
        try:
            self.backup_file({"dst_path": "/flash/OTA_VERSION.py"})
        except OSError:
            pass  # There isnt a previous file to backup
        with open("/flash/OTA_VERSION.py", 'w') as fp:
            fp.write("VERSION = '{}'".format(manifest['version']))
        from OTA_VERSION import VERSION

        # Reboot the device to run the new decode
        machine.reset()

    def get_file(self, f):
        new_path = "{}.new".format(f['dst_path'])

        # If a .new file exists from a previously failed update delete it
        try:
            os.remove(new_path)
        except OSError:
            pass  # The file didnt exist

        # Download new file with a .new extension to not overwrite the existing
        # file until the hash is verified.
        hash = self.get_data(f['URL'].split("/", 3)[-1],
                             dest_path=new_path,
                             hash=True)

        # Hash mismatch
        if hash != f['hash']:
            print(hash, f['hash'])
            msg = "Downloaded file's hash does not match expected hash"
            raise Exception(msg)

    def backup_file(self, f):
        bak_path = "{}.bak".format(f['dst_path'])
        dest_path = "{}".format(f['dst_path'])

        # Delete previous backup if it exists
        try:
            os.remove(bak_path)
        except OSError:
            pass  # There isnt a previous backup

        # Backup current file
        os.rename(dest_path, bak_path)

    def delete_file(self, f):
        bak_path = "/{}.bak_del".format(f)
        dest_path = "/{}".format(f)

        # Delete previous delete backup if it exists
        try:
            os.remove(bak_path)
        except OSError:
            pass  # There isnt a previous delete backup

        # Backup current file
        # if it exists
        try:
            os.stat(dest_path)#raises exception if file does not exist
            os.rename(dest_path, bak_path)
        except:
            print("Warning: could not delete (rename to .bak_del) the file ",dest_path)

    def write_firmware(self, f):
        hash = self.get_data(f['URL'].split("/", 3)[-1],
                             hash=True,
                             firmware=True)
        # TODO: Add verification when released in future firmware


class WiFiOTA(OTA):
    def __init__(self, ssid, password, ip, port):
        self.SSID = ssid
        self.password = password
        self.ip = ip
        self.port = port

    def connect(self):
        self.wlan = network.WLAN(mode=network.WLAN.STA)
        if not self.wlan.isconnected() or self.wlan.ssid() != self.SSID:
            for net in self.wlan.scan():
                if net.ssid == self.SSID:
                    self.wlan.connect(self.SSID, auth=(network.WLAN.WPA2,
                                                       self.password))
                    while not self.wlan.isconnected():
                        machine.idle()  # save power while waiting
                    break
            else:
                raise Exception("Cannot find network '{}'".format(SSID))
        else:
            # Already connected to the correct WiFi
            pass

    def _http_get(self, path, host):
        req_fmt = 'GET /{} HTTP/1.0\r\nHost: {}\r\n\r\n'
        req = bytes(req_fmt.format(path, host), 'utf8')
        return req

    def get_data(self, req, dest_path=None, hash=False, firmware=False):
        h = None

        # Connect to server
        print("Requesting: {}".format(req))
        s = socket.socket(socket.AF_INET,
                          socket.SOCK_STREAM,
                          socket.IPPROTO_TCP)
        s.connect((self.ip, self.port))

        # Request File
        s.sendall(self._http_get(req, "{}:{}".format(self.ip, self.port)))

        try:
            content = bytearray()
            fp = None
            if dest_path is not None:
                if firmware:
                    raise Exception("Cannot write firmware to a file")
                fp = open(dest_path, 'wb')

            if firmware:
                pycom.ota_start()

            h = uhashlib.sha1()

            # Get data from server
            result = s.recv(100)

            start_writing = False
            while (len(result) > 0):
                # Ignore the HTTP headers
                if not start_writing:
                    if "\r\n\r\n" in result:
                        start_writing = True
                        result = result.decode().split("\r\n\r\n")[1].encode()

                if start_writing:
                    if firmware:
                        pycom.ota_write(result)
                    elif fp is None:
                        content.extend(result)
                    else:
                        fp.write(result)

                    if hash:
                        h.update(result)

                result = s.recv(100)

            s.close()

            if fp is not None:
                fp.close()
            if firmware:
                pycom.ota_finish()

        except Exception as e:
            # Since only one hash operation is allowed at Once
            # ensure we close it if there is an error
            if h is not None:
                h.digest()
            raise e

        hash_val = ubinascii.hexlify(h.digest()).decode()

        if dest_path is None:
            if hash:
                return (bytes(content), hash_val)
            else:
                return bytes(content)
        elif hash:
            return hash_val
     

# Turn on GREEN LED
pycom.heartbeat(False)
pycom.rgbled(0x00ff00)

# Setup OTA
ota = WiFiOTA(WIFI_SSID,
              WIFI_PW,
              SERVER_IP,  # Update server address
              8000)  # Update server port


while True:

    # Some sort of OTA trigger
    if True:
        print("Current Version: ",VERSION)
        print("Performing OTA")
        # Perform OTA
        try:
            ota.connect()
            ota.update()
        except Exception as e:
            sys.print_exception(e)
    sleep(5)