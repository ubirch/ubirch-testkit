#!/usr/bin/env python
# Based on example OTA code from pycom which is from
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

import sys
import machine

#exit bootloader immediately if this is a deepsleep loop
if (machine.reset_cause() == machine.DEEPSLEEP_RESET):
    print("Deepsleep reset, skipping OTA bootloader")
    sys.exit()

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
import time
from time import sleep
import ubinascii
import ucrypto
from network import LTE
#only add compiled-in libraries above for reliability
#other code should be directly contained in boot.py

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
    PUB_MOD_RSA_4096 = "CD01EC4B10F718BAD46F177EFFD64B1F4D3FAE655CA5C9E25D5C8B111D8AE8086BC91532CC6BBEE8A4D55B9C39AFA2A3BCAACB02D718FD4316BA744971199B05704601AC80DBDD48D902F333E17913477A66413440754F8717126AB26D3E4432050B73BE27FE028C2F6504799AF8B81B449AB65CC3846BCB1A7DD69C4F7949A93A4181DD9C5835CB69D5C15EA62F47501274E31293772DCC7D44D611C488AD98BE8B350FC6BB5418C6F190156F17AAAF8C64A02CF7CEA16DDBC2D0CD933C459EAF63C51A87F180E85A482C8B2DF172E1C78CEB825297A0A364A2280FB534050C1C12C773495BF9B2A09A85C9BCF8BA5E8D28F1E8E2D743F28188C7039D44ADC4AAB3700D58A2E8F563038C30E8A84E62E8CDB116014838C28C4D77A291F16B8C02F2036958743633763BAB880F7227B910CE256F53718476AF9A738E63AA2B3750FA1C5CA32B34E41A60221EADD230C5090A09A3802A4BE2AF10B8E4F964D36F2E57C186074ACCD9A607ECA2F75B44A401A1A7B52239485054FB11F2EDEA023BAA85C8DA42D8C7D35E595A4ADC3F6A1301AE597989BD679BB5D0C492C7DE732CAD9C27C53B316A9B03673E1A191CED5B84E1239A03D2EEE15F3930FFEA0D977F7200C5B78915C1481CFA81447F40F0B1D53BD1AAFD620A9465D740F96D0732C8C394AE8F14C349AA92F15E4E325F9A0336E877F08355324326E06209FA9C5DBB"       
    PROTOCOL_VERSION = "1.0" #version of the bootloader-server protocol

    # The following two methods need to be implemented in a subclass for the
    # specific transport mechanism e.g. WiFi    

    def connect(self):
        raise NotImplementedError()

    def get_data(self, req, dest_path=None, hash=False):
        raise NotImplementedError()
    
    # The returned id string will be used in the request to the server to make device identification easier
    def get_device_id(self):
        raise NotImplementedError()

    # This method should be called when the update is done to close connections and deinit hardware etc.
    def clean_up(self):
        raise NotImplementedError()

    # OTA methods

    def get_current_version(self):
        try:
            from OTA_VERSION import VERSION
        except ImportError:
            VERSION = '1.0.0'
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
        #generate request id string (based on random bits)
        request_id = ubinascii.hexlify(ucrypto.getrandbits(128)).decode('utf-8')
        req = "manifest.json?current_ver={}&devid={}&reqid={}&protocol={}".format(self.get_current_version(),self.get_device_id(),request_id,self.PROTOCOL_VERSION)
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

        # check that this is the signature we requested and not a replay
        try:
            returned_req_id = manifest['request_id']
        except KeyError:
            raise Exception("Manifest invalid: no request ID returned")
        if returned_req_id != request_id:
            raise Exception("Manifest invalid: returned request ID does not match query request ID")
        
        gc.collect()        
        return manifest

    def update(self):
        manifest = self.get_update_manifest()
        
        #check if we are already on the latest version
        try:
            new_ver = manifest['new_version']
            old_ver = manifest['old_version']
        except KeyError:
            raise Exception("Manifest is invalid: could not parse old/new version information")
        if new_ver == old_ver:
            print("Already on the latest version")
            return

        #check if the manifest was generated for the correct version
        if old_ver != self.get_current_version():
            raise Exception("Manifest is invalid: Manifest is based on version different from the device version")

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
            print("Warning: manifest contains board firmware update, but this is not implemented")
            # This is disabled as the current implementaion does not check the hash/buffers
            # the file and needs to be rewritten
            #self.write_firmware(manifest['firmware'])

        # Save version number
        try:
            self.backup_file({"dst_path": "/flash/OTA_VERSION.py"})
        except OSError:
            pass  # There isnt a previous file to backup
        with open("/flash/OTA_VERSION.py", 'w') as fp:
            fp.write("VERSION = '{}'".format(manifest['new_version']))
        from OTA_VERSION import VERSION

        # Reboot the device to run the new code
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

    # def write_firmware(self, f):
    #     hash = self.get_data(f['URL'].split("/", 3)[-1],
    #                          hash=True,
    #                          firmware=True)
    #     # TODO: Add verification when released in future firmware

class WiFiOTA(OTA):
    def __init__(self, ssid, password, ip, port):
        self.SSID = ssid
        self.password = password
        self.ip = ip
        self.port = port

    
    def get_device_id(self):
        #TODO For Wifi, change this to something like the mac address instead of SIM ICCID
        """Get an identifier for the device used in server requests
        In this case, we return the SHA256 hash of the SIM ICCID prefixed with
        'ID:' and then prepend an 'IC' (for ICCID) so the result is e.g.
        devid = 'IC' + SHA256("ID:12345678901234567890")
              = IC27c6bb74efe9633181ae95bade7740969df13ef15bca1d72a92aa19fb66d24c9"""

        try:
            lte = LTE()
            iccid = lte.iccid()
        except Exception as e:
            print("Getting device ID failed:")
            print(e)
            return "ICERROR"

        hasher = None
        try:
            hasher = uhashlib.sha256("ID:"+iccid)        
            hashvalue = hasher.digest()
        except Exception as e:
            if hasher is not None:
                hasher.digest()#make sure hasher is closed, as only one is allowed at a time by the hardware
            raise e  
        
        devid = "IC" + ubinascii.hexlify(hashvalue).decode('utf-8')

        return devid
    
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

    def clean_up(self):
        if self.wlan.isconnected():
            self.wlan.disconnect()
        self.wlan.deinit()

    def _http_get(self, path, host):
        req_fmt = 'GET /{} HTTP/1.0\r\nHost: {}\r\n\r\n'
        req = bytes(req_fmt.format(path, host), 'utf8')
        return req

    def get_data(self, req, dest_path=None, hash=False):
        # board firmware download is disabled as it needs to
        # be rewritten to not ignore the file hash
        firmware=False

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

class NBIoTOTA(OTA):
    def __init__(self, lte: LTE, apn: str, band: int or None, attachtimeout: int, connecttimeout:int, ip:str, port:int):
        self.lte = lte
        self.apn = apn
        self.band = band
        self.attachtimeout = attachtimeout
        self.connecttimeout = connecttimeout
        self.ip = ip
        self.port = port

    def attach(self):
        if self.lte.isattached():
            return

        sys.stdout.write("Attaching to the NB-IoT network")
        # since we disable unsolicited CEREG messages, as they interfere with AT communication with the SIM via CSIM commands,
        # we are required to use an attach method that does not require cereg messages, for pycom that is legacyattach=false
        self.lte.attach(band=self.band, apn=self.apn,legacyattach=False)
        i = 0
        while not self.lte.isattached() and i < self.attachtimeout:
            i += 1
            time.sleep(1.0)
            sys.stdout.write(".")
        if not self.lte.isattached():
            raise OSError("Timeout when attaching to NB-IoT network.")

        print("\nattached: {} s".format(i))

    def connect(self):
        if self.lte.isconnected():
            return

        if not self.lte.isattached(): self.attach()

        sys.stdout.write("Connecting to the NB-IoT network")
        self.lte.connect()  # start a data session and obtain an IP address
        i = 0
        while not self.lte.isconnected() and i < self.connecttimeout:
            i += 1
            time.sleep(1.0)
            sys.stdout.write(".")
        if not self.lte.isconnected():
            raise OSError("Timeout when connecting to NB-IoT network.")

        print("\nconnected: {} s".format(i))

    def clean_up(self):
        if self.lte.isconnected():
            self.lte.disconnect()
        self.lte.deinit()
    
    def get_device_id(self):
        """Get an identifier for the device used in server requests
        In this case, we return the SHA256 hash of the SIM ICCID prefixed with
        'ID:' and then prepend an 'IC' (for ICCID) so the result is e.g.
        devid = 'IC' + SHA256("ID:12345678901234567890")
              = IC27c6bb74efe9633181ae95bade7740969df13ef15bca1d72a92aa19fb66d24c9"""

        try:
            connection = self.lte.isconnected() #save connection state on entry
            if connection:#we are connected at this point and must pause the data session
                self.lte.pppsuspend()
            iccid = self.lte.iccid()
            if connection:#if there was a connection, resume it
                self.lte.pppresume()
        except Exception as e:
            print("Getting device ID failed:")
            print(e)
            return "ICERROR"

        hasher = None
        try:
            hasher = uhashlib.sha256("ID:"+iccid)        
            hashvalue = hasher.digest()
        except Exception as e:
            if hasher is not None:
                hasher.digest()#make sure hasher is closed, as only one is allowed at a time by the hardware
            raise e  
        
        devid = "IC" + ubinascii.hexlify(hashvalue).decode('utf-8')

        return devid
    
    def _http_get(self, path, host):
        req_fmt = 'GET /{} HTTP/1.0\r\nHost: {}\r\n\r\n'
        req = bytes(req_fmt.format(path, host), 'utf8')
        return req

    def get_data(self, req, dest_path=None, hash=False):
        # board firmware download is disabled as it needs to
        # be rewritten to not ignore the file hash
        firmware=False

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


# helper function to perform the update and keep the OTA
# objects out of global scope (boot.py and main.py have the same scope)
# and thus allow for garbage collection of OTA memory usage later
def check_OTA_update():
    # Configuration (if you are looking for the server pubkey: it's in the OTA class)
    SERVER_IP = "10.42.0.1"
    NBIOT_APN = "iot.1nce.net"
    NBIOT_BAND = None #None = autoscan
    NBIOT_ATTACH_TIMEOUT = 15*60 #seconds
    NBIOT_CONNECT_TIMEOUT = 15*60 #seconds
    WATCHDOG_TIMEOUT =  15*60*1000 #milliseconds

    #setup watchdog
    wdt = machine.WDT(timeout=WATCHDOG_TIMEOUT)
    wdt.feed()   
    
    try:
        # Setup Wifi OTA
        from ota_wifi_secrets import WIFI_SSID, WIFI_PW
        ota = WiFiOTA(WIFI_SSID,
                WIFI_PW,
                SERVER_IP,  # server address
                8000)  # server port
        
        # # Setup NB-IoT OTA
        # print("Initializing LTE")
        # lte = LTE()
        # lte.reset()
        # lte.init()

        # ota = NBIoTOTA(lte,
        #         NBIOT_APN, 
        #         NBIOT_BAND,
        #         NBIOT_ATTACH_TIMEOUT,
        #         NBIOT_CONNECT_TIMEOUT,    
        #         SERVER_IP,  # server address
        #         8000)  # server port

        #start the update itself
        print("Current version: ", ota.get_current_version())
        ota.connect()
        ota.update()
    except Exception as e:
        raise(e)#let top level loop handle exception
    finally:
        if ota is not None:
            ota.clean_up()
        # before leaving, set watchdog to large value, so we don't interfere 
        # with code in main.py (wdt can never be disabled after use)
        wdt = machine.WDT(timeout=10*24*60*60*1000)
        wdt.feed()

### start main code ###

# Turn on GREEN LED
print("\nEntering OTA bootloader")
pycom.heartbeat(False)
pycom.rgbled(0x000500)

ota_max_retries = 3
for retries_left in range((ota_max_retries-1),-1,-1):
    try:         
        print("\nStarting OTA update")        
        check_OTA_update()
        break # leave retry for loop if successful
    except Exception as e:
        print("Exception occured during OTA update:")
        sys.print_exception(e)
        if retries_left > 0:
            print("Retrying update")
        else:
            print("Giving up")
        
gc.collect() #free up memory that was used by OTA objects
print("\nLeaving OTA bootloader")