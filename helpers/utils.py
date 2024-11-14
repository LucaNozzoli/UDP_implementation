import hashlib

def generate_checksum(data):
    return hashlib.md5(data).hexdigest()

def verify_checksum(data, checksum):
    return hashlib.md5(data).hexdigest() == checksum