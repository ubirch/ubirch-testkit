"""HMAC (Keyed-Hashing for Message Authentication) Python module.
Implements the HMAC algorithm as described by RFC 2104.
"""

import hashlib as _hashlib

trans_5C = bytes((x ^ 0x5C) for x in range(256))
trans_36 = bytes((x ^ 0x36) for x in range(256))

def translate(d, t):
    return bytes(t[x] for x in d)

# The size of the digests returned by HMAC depends on the underlying
# hashing module used.  Use digest_size from the instance of HMAC instead.
digest_size = None



class HMAC:
    """RFC 2104 HMAC class.  Also complies with RFC 4231.
    This supports the API for Cryptographic Hash Functions (PEP 247).
    """
    blocksize = 64  # 512-bit HMAC; can be changed in subclasses.

    def __init__(self, key, msg = None, digestmod = None):
        """Create a new HMAC object.
        key:       key for the keyed hash object.
        msg:       Initial input for the hash, if provided.
        digestmod: A module supporting PEP 247.  *OR*
                   A hashlib constructor returning a new hash object. *OR*
                   A hash name suitable for hashlib.new().
                   Defaults to hashlib.md5.
                   Implicit default to hashlib.md5 is deprecated and will be
                   removed in Python 3.6.
        Note: key and msg must be a bytes or bytearray objects.
        """

        if not isinstance(key, (bytes, bytearray)):
            raise TypeError("key: expected bytes or bytearray, but got %r" % type(key).__name__)

        if digestmod is None:
            raise Exception("HMAC() without an explicit digestmod argument "
                           "is deprecated.")

        if callable(digestmod):
            self.digest_cons = digestmod
        elif isinstance(digestmod, str):
            self.digest_cons = lambda d=b'': _hashlib.new(digestmod, d)
        else:
            self.digest_cons = lambda d=b'': digestmod.new(d)

        self.inner = self.digest_cons()
        self.digest_size = 32
        self.block_size = 64

        if len(key) > self.block_size:
            raise Exception('key too long')

        key = key + bytes(self.block_size - len(key))
        self.inner.update(translate(key, trans_36))
        self.outer_key_translated = translate(key, trans_5C)
        if msg is not None:
            self.update(msg)

    @property
    def name(self):
        return "hmac-" + self.inner.name

    def update(self, msg):
        """Update this hashing object with the string msg.
        """
        self.inner.update(msg)


    def digest(self):
        """Return the hash value of this hashing object.
        This returns a string containing 8-bit data.  The object is
        not altered in any way by this function; you can continue
        updating the object after calling this function.
        """
        inner_digest = self.inner.digest()
        self.outer = self.digest_cons()
        self.outer.update(self.outer_key_translated)
        self.outer.update(inner_digest)
        return self.outer.digest()


def new(key, msg = None, digestmod = None):
    """Create a new hashing object and return it.
    key: The starting key for the hash.
    msg: if available, will immediately be hashed into the object's starting
    state.
    You can now feed arbitrary strings into the object using its update()
    method, and can ask for the hash value at any time by calling its digest()
    method.
    """
    return HMAC(key, msg, digestmod)
