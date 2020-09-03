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
import math
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

#RSA PKCS1 PSS crypto functions
#This was ported to micropython based on the pycrypto library function in PKCS1_PSS.py
#See https://github.com/pycrypto/pycrypto/blob/7acba5f3a6ff10f1424c309d0d34d2b713233019/lib/Crypto/Signature/PKCS1_PSS.py

def get_hash(data):
    hasher = uhashlib.sha256(data)
    return hasher.digest()

def byte_xor(ba1, ba2):
    return bytes([_a ^ _b for _a, _b in zip(ba1, ba2)])

def modular_pow(message_int, exp_int, n_int):
    """Perform RSA function by exponentiation of message to exp with modulus n, all public.
    Only use with public parameters, as it will leak information about them. Micropython ints can be (almost) arbitrarily large.
    Based on micropython implementation from 
    https://github.com/artem-smotrakov/esp32-weather-google-sheets/blob/841722fd67404588bfd29c15def897c9f8e967e3/src/rsa/common.py
    """
    #TODO: implement assert function
    #assert_int(message, 'message')
    #assert_int(exp, 'exp')
    #assert_int(n, 'n')

    if message_int < 0:
        raise Exception('Only non-negative numbers are supported')

    if message_int > n_int:
        raise Exception("The message %i is too long for n=%i" % (message_int, n_int))

    if n_int == 1:
        return 0
    # Assert :: (n - 1) * (n - 1) does not overflow message
    result = 1
    message_int = message_int % n_int
    while  exp_int > 0:
        if  exp_int % 2 == 1:
            result = (result * message_int) % n_int
        exp_int =  exp_int >> 1
        message_int = (message_int * message_int) % n_int
    return result

def EMSA_PSS_VERIFY(mhash, em, emBits, sLen):
    """
    Implement the ``EMSA-PSS-VERIFY`` function, as defined
    in PKCS#1 v2.1 (RFC3447, 9.1.2). 
    ``EMSA-PSS-VERIFY`` actually accepts the message ``M`` as input,
    and hash it internally. Here, we expect that the message has already
    been hashed instead.
    :Parameters:
     mhash : Byte array that holds the digest of the message to be verified.
     em : bytes
            The signature to verify, therefore proving that the sender really signed
            the message that was received.
     emBits : int
            Length of the final encoding (em), in bits.
     sLen : int
            Length of the salt, in bytes.
    :Return: 0 if the encoding is consistent, 1 if it is inconsistent.
    :Raise ValueError:
        When digest or salt length are too big.
    """

    emLen = math.ceil(emBits/8)

    hLen = len(mhash)

    # Bitmask of digits that fill up
    lmask = 0
    for i in range(8*emLen-emBits):#was xrange before
        lmask = lmask>>1 | 0x80

    # Step 1 and 2 have been already done
    # Step 3
    if emLen < hLen+sLen+2:
        return False
    # Step 4
    if ord(em[-1:])!=0xBC:
        return False
    # Step 5
    maskedDB = em[:emLen-hLen-1]
    h = em[emLen-hLen-1:-1]
    # Step 6
    if lmask & em[0]:
        return False
    # Step 7
    dbMask = MGF1(h, emLen-hLen-1)
    # Step 8
    db = byte_xor(maskedDB, dbMask)
    # Step 9
    db = ((db[0]) & ~lmask).to_bytes(1,'big') + db[1:]
    # Step 10
    if not db.startswith((b'\x00')*(emLen-hLen-sLen-2) + (b'\x01')):
        return False
    # Step 11
    salt = b''
    if sLen: salt = db[-sLen:]
    # Step 12 and 13
    hp =get_hash((b'\x00')*8 + mhash + salt)
    # Step 14
    if h!=hp:
        return False
    return True

def MGF1(mgfSeed, maskLen):
    """Mask Generation Function, described in B.2.1"""
    T = b''
    hashsize = len(get_hash(""))
    for counter in range(math.ceil(maskLen/hashsize)):
        c = counter.to_bytes(4,'big')
        T = T + get_hash(mgfSeed + c)
    assert(len(T)>=maskLen)
    return T[:maskLen]


def verify_pkcs1_pss(mhash, signature_hex, pub_modulus_hex):
        """Verify that a certain PKCS#1 PSS signature is authentic.     
    
        This function checks if the party holding the private half of the given
        RSA key has really signed the message. These functions are currently
        hardcoded to 2048 bit and SHA256
    
        This function is called ``RSASSA-PSS-VERIFY``, and is specified in section
        8.1.2 of RFC3447.
    
        :Parameters:
         mhash : bytes
                The hash that was carried out over the message as raw bytes
         signature_hex : hex string
                The signature that needs to be validated.
         pub_modulus_hex : hex string
                The public modulus (pubkey) for verification.
    
        :Return: True if verification is correct. False otherwise.

        This was ported to micropython based on the pycrypto library function in PKCS1_PSS.py
        See https://github.com/pycrypto/pycrypto/blob/7acba5f3a6ff10f1424c309d0d34d2b713233019/lib/Crypto/Signature/PKCS1_PSS.py
        """    
        #public exponententas standardized
        pub_exponent = 65537
        
        # salt length is assumed to be same as number of bytes in hash
        sLen = 32 #we only support SHA256 as digest 
        
        #Check hash has correct length
        if len(mhash) != len(get_hash("0")):
            print("Warning: Can't check signature, hash size is invalid.")
            return False
        
  
        #parse other parameters
        modBits = 2048 # hardcoded 2048 bit keys
        signature = ubinascii.unhexlify(signature_hex) 
        #pub_modulus_string = "00baaa1a7d98bf662fdd0744e7a7fb83fe41f5613afc43b630013be7e52e4fae9e90634c358fa8ce724721e8a80a5a67978fb88cba9793517b7ab8997ee8b502a9f2933b77b3be0e72cbfe6746da8c081cf5fc8383e4de13b72c20a6e38e5750f1d8bdc1f4ae7e6289a1e664c6aec7cd341959e1506a2e5850385550a3e4cb1b77a3cb6a30b55a746e708000a0d1bddab38c05654c5c85d91d8a658ffc186bd0f46036eb2cd577b44eface5cb50d4de0213cfa2e9f96ad9e7172c3bb0fe550ddc92b86f45033cf62b3dc9942d198c9cb3e0a83d105e25fcf83f2d16bad31fc5eaa5d0e9281a059819f8b94c9a01aa613c1ed21a878cb65a66ca656b170857e79e3"
        pub_modulus = ubinascii.unhexlify(pub_modulus_hex)
        pub_modulus_int = int.from_bytes(pub_modulus, 'big')
        
        # See 8.1.2 in RFC3447
        k = math.ceil(modBits/8) 
        # Step 1
        if len(signature) != k:
            print("Warning: Can't check signature, signature length wrong.")
            return False
        # Step 2a (O2SIP), 2b (RSAVP1), and partially 2c (I2OSP)
        # Note that signature must be smaller than the module
        # but we won't complain about it (here).       
        sig_int = int.from_bytes(signature, 'big')        
        m = modular_pow(sig_int,pub_exponent, pub_modulus_int)
        # Step 2c (convert m int to em octet string)
        emLen = math.ceil((modBits-1)/8)
        em = m.to_bytes(emLen,'big')
        # Step 3
        try:
            result = EMSA_PSS_VERIFY(mhash, em, modBits-1, sLen)
        except ValueError:
            return False
        # Step 4
        return result

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
        #TODO: add salt to request
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
            print("Test start")
            h = uhashlib.sha256()
            h.update("To be signed")
            hashsum = h.digest()
            print(verify_pkcs1_pss(hashsum,
                    "9643f49f19eac094f962f48e866650da946ad975b55381da800ad69fe762b4efa4bec343f68c7adfa5aac5a91ebf4c958a637f7159d845fec0d36fcb08d8e6057c3b9254497a8b842b5f819c941a27a21c08654169ce72b0cf3a35ea66e54ac8a7d2a7daa1309380e0ecf5d1fa081e98f76d45edfcf1211604bb43e8c4c5144a54de2c9e7831526d34b60935d306e42a216519f38eda51b2ffba284c01c20ec72e9bbba04010ff9a5554796628be7ecb1b0587dcab89b17828b8b3eb4317acc5c4980855db1e97697913a13b832ea8045391bb221917500563c17beb317896a088f3b73a0e652a74d9ff4e19138e0241021184ee60935931e142b3a40e42882f",
                    "00baaa1a7d98bf662fdd0744e7a7fb83fe41f5613afc43b630013be7e52e4fae9e90634c358fa8ce724721e8a80a5a67978fb88cba9793517b7ab8997ee8b502a9f2933b77b3be0e72cbfe6746da8c081cf5fc8383e4de13b72c20a6e38e5750f1d8bdc1f4ae7e6289a1e664c6aec7cd341959e1506a2e5850385550a3e4cb1b77a3cb6a30b55a746e708000a0d1bddab38c05654c5c85d91d8a658ffc186bd0f46036eb2cd577b44eface5cb50d4de0213cfa2e9f96ad9e7172c3bb0fe550ddc92b86f45033cf62b3dc9942d198c9cb3e0a83d105e25fcf83f2d16bad31fc5eaa5d0e9281a059819f8b94c9a01aa613c1ed21a878cb65a66ca656b170857e79e3"
                    ))
            print("Test end")
            #ota.connect()
            #ota.update()
        except Exception as e:
            sys.print_exception(e)
    sleep(5)