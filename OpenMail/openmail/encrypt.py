# simple encrypt/decrypt support.
# dependencies: Padding, PyCrypto

import hashlib
import random
from Crypto.Cipher import AES
from config import CONFIG

class MyCrypto(object):

    @classmethod
    def decrypt(self, data):
        import Padding
        passwd = CONFIG.master_passwd  # this needs to be in a secure store...
        iv, enc_data = data[:16], data[16:]
        print(len(iv),type(iv))
        decryptor = AES.new(hashlib.sha256(passwd).digest(), AES.MODE_CBC, iv)
        padded_data = decryptor.decrypt(enc_data)
        orig_data = Padding.removePadding(padded_data)
        return orig_data

    @classmethod
    def encrypt(self, data):  # TODO
        import Padding
        output = ''
        passwd = CONFIG.master_passwd
        # now, encrypt
        padded_data = Padding.appendPadding(data)
        iv = ''.join(chr(random.randint(0, 0xff)) for i in range(16))  # random vector
        encryptor = AES.new(hashlib.sha256(passwd).digest(), AES.MODE_CBC, iv)
        size = len(data)
        output += iv
        output += encryptor.encrypt(padded_data)
        return output
