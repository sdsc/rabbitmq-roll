# configuration stuff

# masters - hosts that can issue commands to the cluster and can provide the cluster key
Masters = [ 'hpcdev-pub03.sdsc.edu' ]

# constants 
CLUSTER_KEY_FILE='/var/tmp/clusterkey'
PRIVATE_KEY_FILE='/etc/ssh/ssh_host_rsa_key'
KNOWN_HOSTS_FILE='/etc/ssh/ssh_known_hosts'
REPLAY_CACHE_FILE='/tmp/replaycache'

# we'll need a HostKey object so we can look up ssh keys.
# do this once at startup to reduce message sending overhead
#from paramiko import HostKeys
#hostKeys = HostKeys(KNOWN_HOSTS_FILE)

# initialize the replay nonce to some random number
# while it would suffice to use a new nonce for each message
# it's a little slower than just incrementing this number.
from struct import unpack
import os
replayNonce = unpack('Q', os.urandom(8))[0]

# how long do messages live? (in milliseconds / 10E-3 seconds)
# this MUST BE A STRING
MSG_TTL = '300000'

