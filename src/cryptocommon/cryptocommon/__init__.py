# crypto.py - cryptographic routines

import logging
import config
import re
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Signature import PKCS1_PSS
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
from base64 import b64encode, b64decode
import time
import anydbm
import os

# globals
KEY_SIZE=32
IV_SIZE=16

logger = logging.getLogger('cryptoclient.CryptoClient')
def setSignMessage(msg, properties):
    """Set some mandatory fields in properties (pika.BasicProperties), add signature header to properties.  Signed using key in PRIVATE_KEY_FILE."""

    # replayNonce to prevent replay attacks
    config.replayNonce += 1
    properties.message_id = str(config.replayNonce)

    # time so we know when the message was created
    properties.timestamp = time.time()

    # expiration so we know when the message is to old to act on
    # also needed for replay attack mitigation
    properties.expiration = config.MSG_TTL

    signMessage(msg=msg, properties=properties)


def digestMessage(msg, properties):
    """Create a digest (sha256 mhash object) of msg and its properties (pika.BasicProperties). You probably want to call digest() of the result."""

    # from spec: Publisher performs SHA2-256 digest of the following 
    # (in this specific order):
    # message id | type | timestamp | expiration | body | reply_to 
    digest = SHA256.new()
    digest.update(properties.message_id)
    digest.update('|')
    digest.update(properties.type)
    digest.update('|')
    digest.update(str(properties.timestamp))
    digest.update('|')
    digest.update(properties.expiration)
    digest.update('|')
    digest.update(msg)
    digest.update('|')
    digest.update(properties.reply_to)
    return digest


def signMessage(msg, properties):
    """Sign the outgoing amqp message using key in PRIVATE_KEY_FILE, adds signature header to properties"""

    digest = digestMessage(msg=msg, properties=properties)

    # encrypt digest with our private key
    f = open(config.PRIVATE_KEY_FILE, 'r')
    privKey = RSA.importKey(f.read())
    f.close()
    from Crypto.Signature import PKCS1_PSS
    signer = PKCS1_PSS.new(privKey)
    sig = signer.sign(digest)

    properties.headers = dict(signature = b64encode(sig))

def verifyMessage(expectedSrcs, msg, properties):
    """Verify the integrity of the message.  Provide a dictionary of expected sources to check the signature against.  Will perform replay checks.  Returns verified message or None"""
    # check origin and sigs first. No point in processing forged messages.
    if properties.reply_to == None:
        logger.error("No reply_to")
        return None

    if properties.reply_to not in expectedSrcs:
	    logger.error("Msg not from expected source")
	    return None

    pubKeyRaw = readHostKey(properties.reply_to)
    if pubKeyRaw is None:
        logger.error("No pubKeyRaw")
        return None

    pubKey = RSA.importKey('ssh-rsa %s'%pubKeyRaw)
    expectedSig = b64decode(properties.headers.get('signature'))
    observedDigest = digestMessage(msg=msg, properties=properties)
    v = PKCS1_PSS.new(pubKey)
    if not v.verify(observedDigest, expectedSig):
        logger.error("Failed to verify signature %s"%(b64encode(expectedSig)))
        return None

    # message expired?
    now = time.time()
    expires = (int(properties.expiration) / 1000) + int(properties.timestamp)
    if expires <= now:
        logging.getLogger('cryptoclient.CryptoClient').error("Message expired $ss ago"%str(now-expires))
        return None

    # anti-replay check
    id = "%s|%s"%(properties.reply_to, properties.message_id)
    db = anydbm.open(config.REPLAY_CACHE_FILE, 'c')
    # note old entries (don't delete here since it screws up the iterator)
    oldEntries = []
    for h,exp in db.iteritems():
        if int(exp) <= now:
            oldEntries.append(h)
    for h in oldEntries:
        del db[h]
    if id in db.keys():
        logger.error("replay detected: %s"%id)
        return None

    # add this message to the replay cache
    db[id] = str(expires)
    db.close()

    # guess it's good.
    return msg
    

def RsaDecrypt(msg):
    """Decrypt msg with our private key.  Do not use for large messages.  Corresponds to RsaEncrypt()"""
    with open(config.PRIVATE_KEY_FILE, 'r') as f:
        privKey = RSA.importKey(f.read())
        srcCipher = PKCS1_OAEP.new(privKey)
        return(srcCipher.decrypt(msg))

    
def RsaEncrypt(dstHost, msg):
    """Encrypt msg with public key for dstHost (so dstHost can decrypt with its private key).  Note that msg must be relatively small, ~256 bytes, and they payload will not be authenticated."""

    dstKey = readHostKey(dstHost)
    if dstKey == None:
	print 'Unable to locate public key for {} in file {}'.format(dstHost, config.KNOWN_HOSTS_FILE)
	return()

    dstKey = RSA.importKey('ssh-rsa {}'.format(dstKey))
    dstCipher = PKCS1_OAEP.new(dstKey)
    return dstCipher.encrypt(msg)


def readHostKey(host):
    """Read a host key from the known hosts file"""

    try:
        from paramiko import HostKeys
        hostKeys = HostKeys(config.KNOWN_HOSTS_FILE)
        k = hostKeys.lookup(host)['ssh-rsa']
        return(k.get_base64())
    except TypeError:
        return None


def clusterEncrypt(clusterKey, msg):
    """Encrypt msg using AES and clusterKey"""

    global IV_SIZE
    global KEY_SIZE

    # If a producer, no keyex was done, but we'll have the cluster key locally.
    if clusterKey == None:
	print "Loading cluster key"
	import keyex
	clusterKey = read_cluster_key()

    # create a random IV
    iv = os.urandom(IV_SIZE)
    if len(iv) != IV_SIZE:
	raise Exception("IV is wrong size. Tried to read {} bytes from urandom".format(IV_SIZE))

    # sanity-check the key
    if len(clusterKey) != KEY_SIZE:
	raise Exception("Cluster key is wrong size. Expecting {} bytes, got {}".format(KEY_SIZE, len(clusterKey)))

    # encrypt
    cipher = AES.new(clusterKey, AES.MODE_OPENPGP, iv)
    return cipher.encrypt(msg)


def clusterDecrypt(clusterKey, ciphertext):
    """Decrypt msg using AES and clusterKey"""
    cipher = AES.new(clusterKey, AES.MODE_OPENPGP, ciphertext[:IV_SIZE+2])
    return cipher.decrypt(ciphertext[IV_SIZE+2:])

def read_cluster_key():
    """Read the cluster key from CLUSTER_KEY_FILE. Generate one if needed"""

    try:
        f = open(config.CLUSTER_KEY_FILE, 'r')
        key = f.read()
        if key == "":
            generate_cluster_key()
    except IOError:
        # sometimes the file doesn't exist.
        generate_cluster_key()

    with open(config.CLUSTER_KEY_FILE, 'r') as f:
        key = f.read()

    if key == "":
        raise Exception('Unable to read key from {}; unable to write one too.'.format(config.CLUSTER_KEY_FILE))

    return key


def generate_cluster_key():
    """Generate a cluster key and write it to CLUSTER_KEY_FILE"""
    
    # does file exist?
    if os.path.isfile(config.CLUSTER_KEY_FILE):
        # it better be empty.
        if os.path.getsize(config.CLUSTER_KEY_FILE) > 0:
            raise Exception('Key file not empty'.format(config.CLUSTER_KEY_FILE))

    with open(config.CLUSTER_KEY_FILE, 'w') as f:
        # generate a key
        tmpkey = os.urandom(32)
        if len(tmpkey) != 32:
            raise Exception('Only got {} bytes from os.urandom(), expected {}'.format(len(tmpkey), 32))

        # write it
        f.seek(0)
        f.write(tmpkey)
        tmpkey = ''
