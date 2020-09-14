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
#only add compiled-in libraries above for reliability
#other code should be directly contained in boot.py

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

class PKCS1_PSSVerifier():
    def __init__(self,hasher=uhashlib.sha256):
        self.hasher = hasher

    def __get_hash(self,data):
        hasher = None
        try:
            hasher = self.hasher(data)        
            return hasher.digest()
        except Exception as e:
            if hasher is not None:
                hasher.digest()#make sure hasher is closed, as only one is allowed at a time by the hardware
            raise e    

    def __byte_xor(self,ba1, ba2):
        return bytes([_a ^ _b for _a, _b in zip(ba1, ba2)])

    def __modular_pow_public(self,message_int, exp_int, n_int):
        """Perform RSA function by exponentiation of message (= signature data) to exp with modulus n, all public.
        Only use with public parameters, as it will leak information about them. Micropython ints can be (almost) arbitrarily large.
        Based on micropython implementation from 
        https://github.com/artem-smotrakov/esp32-weather-google-sheets/blob/841722fd67404588bfd29c15def897c9f8e967e3/src/rsa/common.py
        (Published under MIT License, Copyright (c) 2019 Artem Smotrakov)
        """

        if not isinstance(message_int,int) or not isinstance(exp_int,int)or not isinstance(n_int,int):
            raise Exception('Only integer inputs are supported')

        if message_int < 0:
            raise Exception('Only non-negative numbers are supported')

        if message_int >= n_int:
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

    def __EMSA_PSS_VERIFY(self,mhash, em, emBits, sLen):
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
        dbMask = self.__MGF1(h, emLen-hLen-1)
        # Step 8
        db = self.__byte_xor(maskedDB, dbMask)
        # Step 9
        db = ((db[0]) & ~lmask).to_bytes(1,'big') + db[1:]
        # Step 10
        if not db.startswith((b'\x00')*(emLen-hLen-sLen-2) + (b'\x01')):
            return False
        # Step 11
        salt = b''
        if sLen: salt = db[-sLen:]
        # Step 12 and 13
        hp =self.__get_hash((b'\x00')*8 + mhash + salt)
        # Step 14
        if h!=hp:
            return False
        return True

    def __MGF1(self,mgfSeed, maskLen):
        """Mask Generation Function, described in B.2.1"""
        T = b''
        hashsize = len(self.__get_hash(""))
        for counter in range(math.ceil(maskLen/hashsize)):
            c = counter.to_bytes(4,'big')
            T = T + self.__get_hash(mgfSeed + c)
        assert(len(T)>=maskLen)
        return T[:maskLen]

    def changehashfunction(self,hasher):
        self.hasher = hasher

    def verify(self,mhash, signature_hex, pub_modulus_hex,pub_exponent = 65537,modBits = 2048):
            """Verify that a certain PKCS#1 PSS signature is authentic.     
        
            This function checks if the party holding the private half of the given
            RSA key has really signed the message. 
        
            This function is called ``RSASSA-PSS-VERIFY``, and is specified in section
            8.1.2 of RFC3447.
        
            :Parameters:
            mhash : bytes
                    The hash that was carried out over the message as raw bytes
            signature_hex : hex string
                    The signature that needs to be validated.
            pub_modulus_hex : hex string
                    The public modulus (pubkey main part) for verification.
            pub_exponent : integer
                    The public exponent (minor info/part of pubkey) for verification. Uses the common 65537 as default.
            modBits : integer
                    The bits the modulo n fits in. Genrally same as key length in bits, Defaults to 2048
        
            :Return: True if verification is correct. False otherwise.

            This was ported to micropython based on the pycrypto library function in PKCS1_PSS.py
            See https://github.com/pycrypto/pycrypto/blob/7acba5f3a6ff10f1424c309d0d34d2b713233019/lib/Crypto/Signature/PKCS1_PSS.py
            (Public domain, no rights reserved.)
            """  

            #Verify input parameters              

            #determine length of hash returned by currently set hash function
            hLen = len(self.__get_hash("0"))
            # salt length is assumed to be same as number of bytes in hash
            sLen = hLen
            
            #Check hash parameter has correct length
            if len(mhash) != hLen:
                print("Warning: Can't check signature, hash size is invalid.")
                return False

            #parse other parameters
            signature = ubinascii.unhexlify(signature_hex) 
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
            m = self.__modular_pow_public(sig_int,pub_exponent, pub_modulus_int)
            # Step 2c (convert m int to em octet string)
            emLen = math.ceil((modBits-1)/8)
            em = m.to_bytes(emLen,'big')
            # Step 3
            try:
                result = self.__EMSA_PSS_VERIFY(mhash, em, modBits-1, sLen)
            except ValueError:
                return False
            # Step 4
            return result


class OTA():
    #set public key (modulus) of OTA server signature here:
    PUB_MOD_RSA_4096 = "00aebbfe89f3913597bb91bc3a22698f54fb94b9e1ecb0f01c9e9f39947e72f9d4ce794ad5004a7e6ec8dbab80950bafdd325f6c09738259a1b3eee6da5b885726df00a5c39c822927488ac0084c1722f466e787d051c53f913e1a4a2e547394af4bab60427dea73c646c6c1a4fafda6a39f0ca84b70f3477eb6bc30ff51ccc16ce208dccc643fece0b7aabc90427b53dee046464b9cc0d36db2af014ffcebf5168a7f588a6fa190dba0bf038c116ce78c8f537392d30a1443fe8a03c7fcc338d4faecdffae78fc9d0b15411a42c7e410255f1936c69a0c15a4464c9e4b2de42b97dcaa09074f029f4b95ec34c5ebbc4667001fe5cef7a4eda7fbd487fd9b23df2fc6c2994a74ecb61e814a80d84c6913890dfc1c19bd7e21148c5ca76ac725c4c3483f7da9ff8deb038889f326a602f8726f20d454712123d5683b1ddc12691fcc04bb82fc07b7dacad6f4f1476e0d84fa2e252832718d4f35c9eee140c8ec752613ee38d10df497736d164d88f6e11566bdae1fd968c4dc4e0d206e0396683eec00dd87418cdbd8ca36312af94cfa8645e7a532073a037598d69d3e5ed1ff14ddd0220a7292c3b0d4a684ebee28e9c6ef0937a86ebb58392a650be7335584fe36ae3d0a983e421c29721272eb2a3ace3605f3c086d2183bdf7f256bd0653053f5e86974b4a97aae7e3db108ad2f9ae679536cf81f3bef61ebe527ab1987c2419"       

    # The following two methods need to be implemented in a subclass for the
    # specific transport mechanism e.g. WiFi    

    def connect(self):
        raise NotImplementedError()

    def get_data(self, req, dest_path=None, hash=False):
        raise NotImplementedError()
    
    #the returned id string will be used in the request to the server to make device identification easier
    def get_device_id(self):
        raise NotImplementedError()

    # OTA methods

    def get_current_version(self):
        return VERSION

    def check_manifest_signature(self,manifest:str,sig_type:str,sig_data:str)->bool:

        if(sig_type=="SIG01_PKCS1_PSS_4096_SHA256"):    
            verifier = PKCS1_PSSVerifier(hasher=uhashlib.sha256)   
            pub_modulus = self.PUB_MOD_RSA_4096
            hasher = uhashlib.sha256(manifest)
            manifest_hash = hasher.digest()
            return verifier.verify(manifest_hash,sig_data,pub_modulus,modBits=4096)
        elif(sig_type=="SIG02_PKCS1_PSS_4096_SHA512"):    
            verifier = PKCS1_PSSVerifier(hasher=uhashlib.sha512)   
            pub_modulus = self.PUB_MOD_RSA_4096
            hasher = uhashlib.sha512(manifest)
            manifest_hash = hasher.digest()
            return verifier.verify(manifest_hash,sig_data,pub_modulus,modBits=4096) 
        else:
            raise Exception("Unknown signature type: {}".format(sig_type))          

        raise Exception("Something is wrong with check_manifest_signature(), you should not have reached this line.")

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
        #TODO: add salt to request, and hashed IMSI or similar ID
        req = "manifest.json?current_ver={}".format(self.get_current_version())
        response = self.get_data(req).decode()

        if len(response)==0 or response is None:
            raise Exception("No response received from server")

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
            print("Signature OK, parsing manifest")    
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
            fp.write("VERSION = '{}'".format(manifest['new_version']))
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
                raise Exception("Cannot find network '{}'".format(self.SSID))
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

            h = uhashlib.sha512()

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
pycom.rgbled(0x000500)

# Setup OTA
ota = WiFiOTA(WIFI_SSID,
              WIFI_PW,
              SERVER_IP,  # Update server address
              8000)  # Update server port

#TODO: add helper function for OTA to allow OTA class to be garbage collected (scope)

def cryptotest():
    print("Crypto test start")
    datastring = "To be signed"
    sigverifier = PKCS1_PSSVerifier()

    key2048="00baaa1a7d98bf662fdd0744e7a7fb83fe41f5613afc43b630013be7e52e4fae9e90634c358fa8ce724721e8a80a5a67978fb88cba9793517b7ab8997ee8b502a9f2933b77b3be0e72cbfe6746da8c081cf5fc8383e4de13b72c20a6e38e5750f1d8bdc1f4ae7e6289a1e664c6aec7cd341959e1506a2e5850385550a3e4cb1b77a3cb6a30b55a746e708000a0d1bddab38c05654c5c85d91d8a658ffc186bd0f46036eb2cd577b44eface5cb50d4de0213cfa2e9f96ad9e7172c3bb0fe550ddc92b86f45033cf62b3dc9942d198c9cb3e0a83d105e25fcf83f2d16bad31fc5eaa5d0e9281a059819f8b94c9a01aa613c1ed21a878cb65a66ca656b170857e79e3"
    key4096="00aebbfe89f3913597bb91bc3a22698f54fb94b9e1ecb0f01c9e9f39947e72f9d4ce794ad5004a7e6ec8dbab80950bafdd325f6c09738259a1b3eee6da5b885726df00a5c39c822927488ac0084c1722f466e787d051c53f913e1a4a2e547394af4bab60427dea73c646c6c1a4fafda6a39f0ca84b70f3477eb6bc30ff51ccc16ce208dccc643fece0b7aabc90427b53dee046464b9cc0d36db2af014ffcebf5168a7f588a6fa190dba0bf038c116ce78c8f537392d30a1443fe8a03c7fcc338d4faecdffae78fc9d0b15411a42c7e410255f1936c69a0c15a4464c9e4b2de42b97dcaa09074f029f4b95ec34c5ebbc4667001fe5cef7a4eda7fbd487fd9b23df2fc6c2994a74ecb61e814a80d84c6913890dfc1c19bd7e21148c5ca76ac725c4c3483f7da9ff8deb038889f326a602f8726f20d454712123d5683b1ddc12691fcc04bb82fc07b7dacad6f4f1476e0d84fa2e252832718d4f35c9eee140c8ec752613ee38d10df497736d164d88f6e11566bdae1fd968c4dc4e0d206e0396683eec00dd87418cdbd8ca36312af94cfa8645e7a532073a037598d69d3e5ed1ff14ddd0220a7292c3b0d4a684ebee28e9c6ef0937a86ebb58392a650be7335584fe36ae3d0a983e421c29721272eb2a3ace3605f3c086d2183bdf7f256bd0653053f5e86974b4a97aae7e3db108ad2f9ae679536cf81f3bef61ebe527ab1987c2419"
    key8192="00babe0067d99d0b9211cf1ff8190a6941a518d96d8b1ecb5d831d5eda6a25c372a2f883a157ccb7a7fc4ed7b301f831ed36de4eb8495e3bf7585e29e30980b3717fb5084959f743af9074aa308ab46a71e2476a15ddcca596832c725bb1ece425f2d52685f31f04b14b24a23dcb12b6bd9244034c7f4a42be5877c4fd17da436291dc9e6a135858d41741e104546e45af6e6d3ada25c1068a923f6deb9b6878b7fb963f243b9ca0f5f199f08adc2460edf60a1200cb06ed34cf550c1ba729950e3e4004632426e6fdac8b29ac97c9b2ac13afda8b9cb65466f8aa96f03014945863c8ad8a90e5d3fe71939415c4954c52babd7e890d460db550ab3fd2f40e5d6b9909792e044d2f6cfc14edc44234eb8623d4473cf7c819b681d0bf8a0d4da2d7dc1449e78fcc7f6cbc827a966c8a25dbd6c73e23c7ec3fb67a01f472aee1e831a46e28b976d4a453a8ca02d1f8a41d8678127a54fd9a00953262f3da75703de29180e958280e4681c2609ee28490aea84b0b1c15ea3702e5f5dbc4197c9867caad33e1a3a41d8c6b42320c745d45d041daab341ca77e06531cb74fd3ef261155acb2b61bebff080e6da44a75bd7c368a4cccbb5e2860cd86ab36d860751067887a737d59a0a8a4a8acf90b2aefe02c8785e62a3dad6cfcb1e812f133f748c4ca34b80625c4320b0925fd4022d7fa41f1a4e1cdda3fd09724ea957a35f53ffcd806c524f2016963dff07c478318dd8d36a54bc54b246414472a47a5909d807af8f7f933ee73c75fe0dd068f30455258a21ff30f88d33041d1901e29300a3bb31b634f0e05c84e4d3966b0ce9f5c03b5731640c848bf6b8d5152889a41527181f2dec3943be832900222966ba55ce018cae9250ae4b83b925234733bf1e6bb627c8c2800e878187423f592fb01e0ed45b73da2d0b00d5ac65cd41b664db5ff07282f5ece430471610f7858aa2e2465f9c0cd69744d69da5274a766e84d3fadf224c49d2d5b7c6088e51445169dcc1fbc0d8bf691719ae885519a1705181a4c0184049bbca1add490aa05472df45ec14d89da09fad7f548a5145365f5a38e0c0923c11f3598ec642b691c43c90771dd0f72505b453ed9f0c05b3db9954157a3b0d4c42638d154eb6cb95687863a0309cc01c970eb14d655c02a9dab3f2cccf59f82a33f969fab9ec15eb8950bcff4b0aa5fb7101374444fdb513f7e130582c484ae534625ebb0f8acff1890ee121d96111653bdcb4a0764dbfdf95a44b8c726631b83f9874fca5cd3b04aecbe94b094219bdf6b1d27eb3ee3eb38baeb29245e2ee64726346fae5ee201322ae18f5ecc8112fe8a902fc880e27c6460da944b7eb4572585686c80d02adc512f6718a476b1d3d17a522c3889ef2593071585a20ca833aa18508832a0faa27038c50b6ce07665a27330bba64556d47e55ddd7663c6759"

    sig2048SHA256="9643f49f19eac094f962f48e866650da946ad975b55381da800ad69fe762b4efa4bec343f68c7adfa5aac5a91ebf4c958a637f7159d845fec0d36fcb08d8e6057c3b9254497a8b842b5f819c941a27a21c08654169ce72b0cf3a35ea66e54ac8a7d2a7daa1309380e0ecf5d1fa081e98f76d45edfcf1211604bb43e8c4c5144a54de2c9e7831526d34b60935d306e42a216519f38eda51b2ffba284c01c20ec72e9bbba04010ff9a5554796628be7ecb1b0587dcab89b17828b8b3eb4317acc5c4980855db1e97697913a13b832ea8045391bb221917500563c17beb317896a088f3b73a0e652a74d9ff4e19138e0241021184ee60935931e142b3a40e42882f"
    sig4096SHA256="a065c4bac23c5a6f3a640c272061caa7d373c81a712ec5b4b89a0d287a16878eea4224a4a83c7818236e0c593fb1bbe0322965b8b2acdf978d6c8c257d8b0c8990fa5935e143f0d17898d743a66f8bd2a22b2171a95783343a7634b4f5a836e6063f7caa7d95a50c474d16df0b5f8f8921f0b1ac092b29143390d501b86acf596f1280f451b8c079f9f2abbf188c07bce64f8b5e4e53f1f8eeb07929d2905c8adab8ef70735432e5adc9eb0147ecd76a0d4cd91a9020dca59c9b120bd2b3276f4deaea0ebfd9a115917a9faccf702ff232a9a8187efb28be034cb98d1394a54b998ed8abae70e5fe23675f528e353edf82e4d8d9f69d982e590e567bc968cde9752978e76c83c38edb8963ab9008f2b60e064cbce35908b5f49eee9723a800d4c4db7ce64c3848e12e8cd049c66df8e65871da8135122ff32173a644abdcf9f12a82282198fb4ac3cc92f3c2dc2706394400351ea7f404007490b393cfa0daed9cb8e3ec003c4cb189a2482675de19eb5213ab4855da23497cfa95ef74fb23dcc2bdf11d478640361954d598fdd6975d15a50c3d8b099ea65f12db7315f35e1892a7de0e9fcb13f181bff1ddb7640bbe6d3b6decdadebae55b383d633d67666c202c33af479e39d14c4bffed41969c864c4eba8ce72ca45bf1582e10e3515133b68144a42566ace909b29dbac07005560ea744676c70e1259441d70a5e619568"
    sig8192SHA256="69c90f5ad4543055a9dc2e8598cb458d34fb75f9f2051f4096c1aafe11f1caf59854328c961971894195e0fd28a474e2037c50154d3c595fd241a7f9044a3336b1ef1790940307d39c5fa327b8245ec12a2680b87f8c014fc37a79b74de8126139ee595c5e39856dd655b367db03027b41967f135e3e075ab87082ce9801f1eba0eeed0370407216bc310e947745865034497afbdca7ecc739f8c1ecbdae9561c770c3d6fb183aa7a825e7f500341c246a6bfc26aa39486146cebdc9bfff829e10c70f6ad58966f4788f4c63e50f0cd13a3ab2c403fb347924a60ef0833b13156f06806a2bf60f717b2d5019886a9b65228b997829e19bfe0acf31764991efce86bf1f744e1d87c380cee39c7dbbc815b541b8ce3f24c41625c019703bd398015cbf769e837ef980f520e0908720569a69cf914109dace295ac5e1f07a3d727fc7d4e8ac56ff1b5a0ff3e484388ff8bbeb6642ec53341fbf8ba64ff8a7a57389b445a039eb8d56f68a95779968254ff1f82b0b339b82122c570b61b02d7acd264ef9ac3c91e857c8640b14dc97814f5828a000b5ca525dfc62695e1f930b7eb3fec6ddf055c188a71cfa9078939afc86c893f66ad7e77c81cb09058b106a3082ed721907a0e1469efc31b8a9e8d87a1b9715fdaef38515918e9cf8bb34d2e812f7d859f00cde7713499cb059cdef25c6337359a59882d4a04d4d8910fb9489bb7de6fca82530e15acc212729c633bc1a4ea19e1ad0965c098562232ea129f8c8a19015b857a0c93b755e58e3c67e21f724ae18bba0b1361b900915c614338f74891dcb1eb652987f91b04a9985e82687959495f2e7f1d2ca964c0483799d780fe85d8a765073460cd5195c8c4ad93bb2a749bc5fdccf0021283339ba4dd42f3ec6647973bebe9d9904e8b07d0c129c64e9efd353c9aa71e20bd4c5f65bcaf0333f8b973fe37e30412012ee78dbe0c9e0f87ef9c4ea00dd3a7122893cb905498e8f23c5a4b3573b978a40e0bfea26d667f932ded4d5385fbef29396e119094ccd81a2cecec371afa5dd7234c66da00eecb6fe5a384fff0bd2eaa9e5a35d255a1a334bc74ed1e99fd59739c401637ad32006911bf1500174889e68931609fe3d7e73d8e3f5e6eb907e6d375594a380929f7c4c341186cba6481a04334997c47b5ef449f4729d5bce169222640be65140b4665ba7b9d346e6384ab7935559b9a50567f3fdf56190901d075ad1c9085e39a289b759147e99f21003d2f34c375dd05761c5f03783b9d11031ad53c4e94c2eaad5f232d41600994423dac7b8e0199041814fa1d18a4c1f97b858d76acc40eff4b64bb7a144e920ae5fc9aae2b8a50e108ae6805616e4234c1207165a60c36397db8dd33eb77efc5943dfcc1e6bb6fd3f438e6be998f7ce9e6e3d20e9542b36ec3b4d9961958a1fe6ccb45af07dfd3a8d"

    sig2048SHA1="120ec2022dbaf14463a0442ec090634ba764364a6630c029420db4a05b7f732b72266a1516a19eae8a38c343d9039a6aa4906aff03b086eea05333734e680756d01c549d564be638968b97c8db33edba75c6874818413854b458ff7130e5df14ed6bfd52395d6d1ea0a7363d1274a94cd43021692a107f0f4fe5cf6dd2aaee0e965c6d8c8bd1d4905c0a9b5fb9f422316e273226290bc47ad213d47138019458340691baa05ab8fbf363e45969034806d03ddf6f9cb13255a6dd45f74a9cd2fb81b328d8ef47801e0d4e2827a7789e4d626bc259b78ff8f13e686f3fe5ebe52a64069c09601250e7f7726339f9a7ee0c9f34e1bf26fe1aea4b2575f7db76a166"
    sig4096SHA1="95b9a8a5dedbe8c4e2d32a79cfc4df7f09f5b0a4d5f78ddb78e8ac7439686c248c1d3af7b7b1ff484d792756d85054c34212e181ffbc8f8f5d326fd6851a144d97b27fc68a032fa91a2ddb8413302353b63466b188a429e8632ce14845b1f2b303912ba0da7af69402c252f7609308e1853fa678115d3943ad5c7d67ca42b2a4becf8b4b9a9b0bca9cc3715951551c65c372a63d361703915dfa03768219017ea4532921c4db06dc439b6628cb8cdcb0d3dfaa6d8400b300847ede6cdbfdccaa254fd7e88b54b545d209b5217b9b8def62124aece24bf2c19e4f9b82a7c7d59b314f2edb95d767779937047e0b2d126dab665c04c2b920a4b4e8b7f7e15ca9609d04f47709e710c19eb58c9b295ddd8c385f10aef11db91e3dd802baee23c6154df822832c5c1348695ce293d08ce5b922b9e41783bd737b56b6123c9384055f6d6208ac4e9ce29e55e2599c706ce12ab95704226ad665b4fb49ccd4ab6ccf9369a23a7d4b96b332af33ac4c45689e503dbb8bb54d290c70eebc1763f0640e2a033fc7f4217944b941d55297a6e09ef5cc6165f21be9ef9cd62a2d2639971dfa053e749b9534ee2284870485e7b9fd23285d745ff26051ad4921917542a08ef8605e29cf23762ba96c9834db00da99f29624b2d2e7df03edf1f4048fe7a010e44680afaf74ece6bb51d3354b30cc304f910c0ba3e718cfb9c7079916063e6761"
    sig8192SHA1="1eca6f4c233064dc55eb8c7bc4b54f9ad6b47e5eeb3e115ed5b6c76c094ea3bc2aac4f0b320b2763a48e3fc61643d879c9aea4ad5e57e6c78028ff48185d82b02a5864445ba189008d32b58fcd0dc05ff02ac673a77486fca0a5ccec262e4dda4a4dc7a253b06aed902982f1abba9b59acc585f1824445e58974e5a3b0c100a7c25ceb2d0f5573875730c122e088486c1536e91704ec2898eac13772979460b2f25a71eb19e73da9b702585059d765b760e2ffce1865fcdf8906ddb20c0ade0f7e8fdd6baf2da217ff104a29423d8511faf5a914d9bb386c0f7e8fbc3ca8ba2fe908d8d28fc3ac9eb6cd423c89ba3dbab0eec542abba8f08b128a9b99f38cd56262b32eba82ff559d1143d88f5ea596249ceccf840fc818ff685ea9dc6f1768335914b7a73fc8e804169252771cccd788fee1b1039a2b6cb973649f549ab9815383fa7228b19fd09e9b6e4691267f622f77984741a49b280a1fc350ee0cc34cf0e19b09c5bd08772720bbd1cf26fb868f9e2ec549f48cf2bbe058bd59a99ce1e3ff24fe37f4cf28cb29f23626a5d2b13f9773ab8dc7e735190b87690a396601a30f0c7fe719c0bd7e7db6a787a980ae48ff21bbe9f8414d2661ad0bf0cdf259d31f618eb86fd5554c5f5834577f44ee9b894dbdf187ae5f1a23007e84e592321f3fc33ebe662e0b07cef9a533cd60f30b9e81e79a251700336854534fed9084b4a116cf0a59e7818db96a4d68a94ce63305982303c9c6e7ba0766665265c22ab961baa470d8208e2240cbf390484c52c7c9f2a4153ab69085c535a34c377c8085bf39b9b0428df932e07b5a41bc98a0488a7cdc00b324bcf5faeb7d3749fca7c76b224b539892b3a62533cbbf2524b76254135b84f732c4031d5ac8e70763dd97d2cb8cdcb68d0b276c4a26d159a823c95db171d235d2ea5c5dbd9abbacc7aa3e40c6ed5dd5b94284b6294130dab6e4389a0cb4707b21ddfa0e8587a5277f1c7230bafd29b580ad6892140d324d83ba76793dfa0bbee56e269ddcf94da885eafb442422af757505ae640c36b210e17789e7dd40f51e629a02845815b03731a31e5c3919f18ada98ccea76597588121691c0e02156e34cac955b0cfc127c64c9f35b24731bc39dfbd5adcd7be8b381ef538e202a4c1f6df7828f1f021d81de8983e56cce8b7e915bdb7c852d87ee950d38b3ae835879a7af20a949f4b6dd7e728bc41198889fd52f4507b29102f2d1beaa74165788bbb627f217df25f064bf4af16cc7ba024aa0d90b0f988d93f4483ac940273253c230ba485cd34ce846f83cbd60a74a7eef8b7fce31e055d7dadeff46982680f8f74238e58a8bec0c6df3dafe397ea1c3371fbc5783040c869b9bb417695ca7a7c389587a38eb31a8d0f5d82148ccdbd81e35c7ab710ca40fdf9de3075e33e24c8a94d1f82e9b3e8a6750bb3"
    
    sig2048SHA512="30abc4e4bffb246823d7e6e5a08516394534f949de2cefd6650cc80bedae1f71a9ef6cde7465af2a94fdc6e480e40065287a899641b1ee316a7ba0fb96a4477692f5f1891509919d0fa7081d91f37737f28aa2c8ccb5c438f341a2b1ca98e92cccc429135f077f8728c479c04004759b4aa4693edfa082920c38c83d960ebf9584c89b318bdd4ddbaa441ace37b85507452df7597c793f6368dc096ece3e3c2ca292f39652fd36a80fdd21bb12c97c7783ac4124804a0434ee50b5993426b77eea7d8253ff4925e604dc6009c7a5abe8372268d1d00a0945db507ac2f08954551fc341fdb5da42321752b56c452a23c641f64426a46c02a236dc66b0ff36890a"
    sig4096SHA512="a09b36e7e61c4007dea85ea3d817a8853bc1cb16f5b9726e7813b6f0d913bf4f58a1239bef55e3192a953838f326e9416ed5bfcc3c66c1fc9051f69cacc6e311e91cfd32fff7b9b199dc688890ec74405da1c346393d104a00b744ec36f071e6db92ad0014431bfd8c1f16bc0f0dc2d8ff67a55d1f4b9e739fdfb05dd30ec98e80b2652906a832c431aeb5ae91c76e27e8c19da079666f1846aaed4730da2b3b98fe98ffbf78048b4ee5a5a1bd9e21092625e24bd7131e9977114056dc0b2438598ab8e4dbabbeedb9e7fe994c7d3fdeab139fb8dbbad217207fae44b6570e66f5d98b1f7677091ee23aa9a9bf8647cd958f07f0b8519ff690bb34dd98d15d85f66f55c531aa8180d820c3fa704929a9fca152c8ecb61fa1fbc2a6f0b624de8b7ca7df88249bb43a5cd8270ffd0a2d34b64c9332e1f46b0f49802332b00c07246318bd078669a68c2a79c12cc17d5809332026ceca47d314b899250c92a6b28a0a9687144a2f041de61770867962534584576c3c514a7b93aac78c09b8fcc43ae724947f23382b9f44ca7a72799a72f5047af8461e33c022da664d7e89b00f4e6e761cf79386b5795cffb50710f1f6228d40e0b5bb53c6d4d86a0484c7334f41b4df0bcd1d2ae72afb2eb08f0fe3c75b0ebf30e72708141406b55eb48b630548bc1ef934e43ce08c8a67ad18f40f2798eecb7bb776b160abc69f27187006e386"
    sig8192SHA512="8e69ed64f923baaa92463081e9684aa045cdd93f09438e36ab8e03b8d7b103352a7fed0e79c538ead47ed312082795041dc179e11e7e274cf51bce3ccd65ebb927ef46f3067fd6db0c6afc84ba13908119acc527dd9f0a4702b7c392ff31b03874b6d7d0fefabd89c9e992784a77dcacd9d169e8aa251de85ef75a677b538c0e3d5f402c51a34fba340c007b7da759a4bdb160dd1352ed9e7f5978e94951daa99a9939732eb125ae10aaf12830619e15104aaac879de147f4100704e52242c522a17a0423b97951564e5794145fd0607ba37cc49779faf8cd816ad6c3076abf3b7f3a1e5fda31ff8a3624b024aedc9b59742f7b3811607b102820d839fdd0ccf69cc3117fce193c3c736d27790266685a18f569fcb2a0f7a12d3f59699dc3d39b2f0681455547c12c060dcaecba3745932bbf4d0ea801b21985fad2345563517489262c10e12031f22913fea93a0382e690a34aa335cae59aada077b3fe8f73cecd1cf06423cc952f85f4fb17a0dd28236554b8feac4f27c8f96db5b117918929d27d4739236c7a798421215287813aa16de5e46e42372efac926bd8ff666f7c4a3b30c48c280af95597a324829b3ba9962e5ec88e1e206e3cf58e62669f686bbeccef434b776c0187c700fe24f6c33b7f16fb320391637f24cde4e8b0326df692e153c26be830069270ac381eebff9f6b54c4620982654252f3f5e751acd31fa657f358165bf7e9c2d79316db02b517679763778988ae58b4c8874fb83d3e3cd9eb384641e5c72fc24fe4f63ae6e140b7bdb4cfe6dded138badd1ce8d3c2ca899e0bc278723cf08a2945a4b1566fcea7daee8efacf6384c2d40c583372f8459284447bed9556cf2b32cb70304f1b6a8ce61353192c7c42c139df1cca9248c2474f08eafacb0500e1d8023c230b7025668da61e6f221bdea2b9acb885964943d469ee6f91cf6dd32ea23e0dd048342f1c6b6ac6d77538b376319e277c84754fd1f9e24a3d11bb26821ed396ebe5abd4f23b4a00ea0d161205c8aaf15febb2533bfc9112efd7abafc916b4ab44ce528ab10c13c8e47376ee77178f1f3c3605ca116c96cda4f73866f4c21bc3ab9d2d7e452e6d8602d2bcc54ca2fee0389debf325549f6785dcef23934f76d527fa76929319cfee4107a989c0e0ba46aae1c07eaa7203a4facf84846b1098747075c6d8f39a69f61d056ab298f627e8cf6bb7e5a087e9dbad2660d0854c2fc37a866b41ff51aa11d9da9ccb3dc092b655d7b267d286374db4222bc3fa3e2f6343d7d56e93126654eacf29ee9ab066665d2abc3824bb01c49f96902e2a008a093c274dff98596a5b48726549e0f15afee5b71b0f99bc0c7f8bf9280811e8f37302767e05a9cbf1d82dda6eb4bf155dbbf6322241257b1c66c6aee7c47b1dd8eae5311f11bd79abdbf7a2a5b38b70e89fdfd740694"

    print("++SHA256++")
    h = uhashlib.sha256(datastring)
    hashsum = h.digest()  
    print("2048bit:")          
    print(sigverifier.verify(hashsum,
            sig2048SHA256,
            key2048,
            modBits=2048
            ))
    print("4096bit:")          
    print(sigverifier.verify(hashsum,
            sig4096SHA256,
            key4096,
            modBits=4096
            ))
    print("8192bit:")          
    print(sigverifier.verify(hashsum,
            sig8192SHA256,
            key8192,
            modBits=8192
            ))

    print("++SHA1++")
    h = uhashlib.sha1(datastring)
    hashsum = h.digest() 
    sigverifier.changehashfunction(uhashlib.sha1) 
    print("2048bit:")          
    print(sigverifier.verify(hashsum,
            sig2048SHA1,
            key2048,
            modBits=2048
            ))
    print("4096bit:")          
    print(sigverifier.verify(hashsum,
            sig4096SHA1,
            key4096,
            modBits=4096
            ))
    print("8192bit:")          
    print(sigverifier.verify(hashsum,
            sig8192SHA1,
            key8192,
            modBits=8192
            ))

    print("++SHA512++")
    h = uhashlib.sha512(datastring)
    hashsum = h.digest() 
    sigverifier.changehashfunction(uhashlib.sha512) 
    print("2048bit:")          
    print(sigverifier.verify(hashsum,
            sig2048SHA512,
            key2048,
            modBits=2048
            ))
    print("4096bit:")          
    print(sigverifier.verify(hashsum,
            sig4096SHA512,
            key4096,
            modBits=4096
            ))
    print("8192bit:")          
    print(sigverifier.verify(hashsum,
            sig8192SHA512,
            key8192,
            modBits=8192
            ))
    print("Crypto test end")

while True:

    # Some sort of OTA trigger
    if True:
        print("Current Version: ",VERSION)
        print("Performing OTA")
        # Perform OTA
        try:
            #cryptotest()
            ota.connect()
            ota.update()
        except Exception as e:
            sys.print_exception(e)
            time.sleep(3)
            machine.reset()
    sleep(5)