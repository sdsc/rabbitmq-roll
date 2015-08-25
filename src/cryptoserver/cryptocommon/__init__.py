# crypto.py - cryptographic routines

import config
import re
from keyex import read_cluster_key
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
clusterKey = None
KEY_SIZE=32
IV_SIZE=16

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
    digest.update(str(int(properties.timestamp)))
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
    # split reply_to into host and routing key
    m = re.search('^(\S+)\|(.+)$', properties.reply_to)
    if m == None:
	return None
    hostname = m.group(1)

    if hostname not in expectedSrcs:
	print "Msg not from expected source"
	return None

    pubKeyRaw = readHostKey(hostname)
    if pubKeyRaw == None:
	return None

    pubKey = RSA.importKey('ssh-rsa {}'.format(pubKeyRaw))
    expectedSig = b64decode(properties.headers.get('signature'))
    observedDigest = digestMessage(msg=msg, properties=properties)
    v = PKCS1_PSS.new(pubKey)
    if not v.verify(observedDigest, expectedSig):
	print "Failed to verify signature"
	return None

    # message expired?
    now = time.time()
    expires = (int(properties.expiration) / 1000) + int(properties.timestamp)
    if expires <= now:
	print "Message expired {}s ago".format(str(now-expires))
	return None
    #print "message expires at {}\n                   {}".format(expires,time.time())

    # anti-replay check
    id = "{}|{}".format(hostname,  properties.message_id)
    db = anydbm.open(config.REPLAY_CACHE_FILE, 'c')
    # note old entries (don't delete here since it screws up the iterator)
    oldEntries = []
    for h,exp in db.iteritems():
	#print "examining {} expires {}".format(h,str(exp))
	if int(exp) <= now:
	    oldEntries.append(h)
    for h in oldEntries:
	del db[h]
    if id in db.keys():
	print "replay detected:{}".format(id)
	return None

    # add this message to the replay cache
    db[id] = str(expires)
    db.close()

    # guess it's good.
    return msg
    

def RsaDecrypt(msg):
    """Decrypt msg with our private key.  Do not use for large messages.  Corresponds to RsaEncrypt()"""
    f = open(config.PRIVATE_KEY_FILE, 'r')
    privKey = RSA.importKey(f.read())
    f.close()
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
	k = config.hostKeys.lookup(host)['ssh-rsa']
	return(k.get_base64())
    except TypeError:
	return None


def clusterEncrypt(msg):
    """Encrypt msg using AES and clusterKey"""

    global clusterKey
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


def clusterDecrypt(ciphertext):
    """Decrypt msg using AES and clusterKey"""
    global IV_SIZE
    
    # clusterKey should have been set already.
    cipher = AES.new(clusterKey, AES.MODE_OPENPGP, ciphertext[:IV_SIZE+2])
    return cipher.decrypt(ciphertext[IV_SIZE+2:])

