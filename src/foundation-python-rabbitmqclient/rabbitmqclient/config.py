# configuration stuff

import os.path

# constants 
CLUSTER_KEY_FILE='/var/tmp/clusterkey'
PRIVATE_KEY_FILE='/etc/ssh/ssh_host_rsa_key'
if(os.path.isfile("/etc/ssh/real_ssh_host_rsa_key")):
    PRIVATE_KEY_FILE='/etc/ssh/real_ssh_host_rsa_key'
KNOWN_HOSTS_FILE='/etc/ssh/ssh_known_hosts'
REPLAY_CACHE_FILE='/tmp/replaycache'

# initialize the replay nonce to some random number
# while it would suffice to use a new nonce for each message
# it's a little slower than just incrementing this number.
from struct import unpack
import os
replayNonce = unpack('Q', os.urandom(8))[0]

# how long do messages live? (in milliseconds / 10E-3 seconds)
# this MUST BE A STRING
MSG_TTL = '300000'
CONN_TIMEOUT = 10 # how long to wait for the key from fe
CONN_RETRIES = 8
