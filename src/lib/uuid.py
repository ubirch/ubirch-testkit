# https://github.com/pfalcon/micropython-lib/blob/master/uuid/uuid.py

import ubinascii


class UUID:
    def __init__(self, bytes):
        if len(bytes) != 16:
            raise ValueError('bytes arg must be 16 bytes long')
        self.bytes = bytes

    @property
    def hex(self):
        return ubinascii.hexlify(self.bytes).decode()

    def __str__(self):
        h = self.hex
        return '-'.join((h[0:8], h[8:12], h[12:16], h[16:20], h[20:32]))

    def __repr__(self):
        return "<UUID: %s>" % str(self)

