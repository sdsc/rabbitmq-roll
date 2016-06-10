#!/opt/rocks/bin/python
# -*- coding: utf-8 -*-

# @Copyright@
#
#                               Rocks(r)
#                        www.rocksclusters.org
#                        version 5.6 (Emerald Boa)
#                        version 6.1 (Emerald Boa)
#
# Copyright (c) 2000 - 2013 The Regents of the University of California.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
# notice unmodified and in its entirety, this list of conditions and the
# following disclaimer in the documentation and/or other materials provided
# with the distribution.
#
# 3. All advertising and press materials, printed or electronic, mentioning
# features or use of this software must display the following acknowledgement:
#
#       "This product includes software developed by the Rocks(r)
#       Cluster Group at the San Diego Supercomputer Center at the
#       University of California, San Diego and its contributors."
#
# 4. Except as permitted for the purposes of acknowledgment in paragraph 3,
# neither the name or logo of this software nor the names of its
# authors may be used to endorse or promote products derived from this
# software without specific prior written permission.  The name of the
# software includes the following terms, and any derivatives thereof:
# "Rocks", "Rocks Clusters", and "Avalanche Installer".  For licensing of
# the associated name, interested parties should contact Technology
# Transfer & Intellectual Property Services, University of California,
# San Diego, 9500 Gilman Drive, Mail Code 0910, La Jolla, CA 92093-0910,
# Ph: (858) 534-5815, FAX: (858) 534-7345, E-MAIL:invent@ucsd.edu
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS''
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# @Copyright@
#

import subprocess
import logging
import os
import pika
import json
import time
import sys
import uuid

from struct import unpack

from Crypto.Hash import SHA256
from base64 import b64encode
from crypto import *
from config import *

from tornado.gen import Task, Return, coroutine
import tornado.process

import rocks.db.helper

class ActionError(Exception):

    pass


def runCommand(params, params2=None):
    try:
        cmd = subprocess.Popen(params, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, shell=False)
    except OSError, e:
        raise ActionError('Command %s failed: %s' % (params[0], str(e)))

    if params2:
        try:
            cmd2 = subprocess.Popen(params2, stdin=cmd.stdout,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, shell=False)
        except OSError, e:
            raise ActionError('Command %s failed: %s' % (params2[0],
                              str(e)))
        cmd.stdout.close()
        (out, err) = cmd2.communicate()
        if cmd2.returncode:
            raise ActionError('Error executing %s: %s' % (params2[0],
                              err))
        else:
            return out.splitlines()
    else:

        (out, err) = cmd.communicate()
        if cmd.returncode:
            raise ActionError('Error executing %s: %s' % (params[0],
                              err))
        else:
            return out.splitlines()

STREAM = tornado.process.Subprocess.STREAM

@coroutine
def runCommandBackground(cmdlist):
    """
    Wrapper around subprocess call using Tornado's Subprocess class.
    This routine can fork a process in the background without blocking the
    main IOloop, the the forked process can run for a long time without
    problem
    """

    LOG = logging.getLogger('imgstorage.imgstoragenas.NasDaemon')
    LOG.debug('Executing: ' + str(cmdlist))

    # tornado.process.initialize()

    sub_process = tornado.process.Subprocess(cmdlist, stdout=STREAM,
            stderr=STREAM, shell=False)

    # we need to set_exit_callback to fetch the return value
    # the function can even be empty by it must be set or the
    # sub_process.returncode will be always None

    retval = 0
    sub_process.set_exit_callback(lambda value: value)

    (result, error) = \
        (yield [Task(sub_process.stdout.read_until_close),
                Task(sub_process.stderr.read_until_close)])

    if sub_process.returncode:
        raise ActionError(error)

    raise Return((result.splitlines(), error))

def setupLogger(logger):
    formatter = \
        logging.Formatter("'%(levelname) -10s %(asctime)s %(name) -30s %(funcName) -35s %(lineno) -5d: %(message)s'"
                          )
    handler = logging.FileHandler('/var/log/rocks/rabbitmq-client.log'
                                  % fname)
    handler.setFormatter(formatter)

    # for log_name in (logger, 'pika.channel', 'pika.connection', 'rabbit_client.RabbitMQClient'):

    for log_name in [logger,
                     'rabbitmqclient.rabbitmqclient.RabbitMQCommonClient'
                     , 'tornado.application']:
        logging.getLogger(log_name).setLevel(logging.DEBUG)
        logging.getLogger(log_name).addHandler(handler)

    return handler


class RabbitMQLocator:

    LOGGER = logging.getLogger(__name__)

    def __init__(self, config_name, read_pw = True):
        if(read_pw):
            with open('/opt/rocks/etc/rabbitmq_%s.conf' % config_name, 'r'
                      ) as rabbit_pw_file:
                self.RABBITMQ_PW = rabbit_pw_file.read().rstrip('\n')
        else:
            self.RABBITMQ_PW = None
        with open('/opt/rocks/etc/rabbitmq.conf', 'r') as \
            rabbit_url_file:
            self.RABBITMQ_URL = rabbit_url_file.read().rstrip('\n')


class RabbitMQCommonClient(object):

    LOGGER = logging.getLogger(__name__)

    def __init__(
        self,
        exchange,
        exchange_type,
        username,
        vhost,
        process_message=None,
        on_open=None,
        routing_key='',
        queue_name='',
        ssl=True, # Use SSL connection
        qos_prefetch=None,
        mandatory=True,
        durable = False,
        encryption = False,
        secur_server = False, # acts as a server having the key
        ssl_options = False, # client certificates
        frontend = None # for certs exchange
        ):
        self._connection = None
        self._channel = None
        self._pub_channel = None
        self._closing = False
        self._consumer_tag = None
        self._key_consumer_tag = None
        locator = RabbitMQLocator(username, read_pw = not ssl_options)
        self._url = locator.RABBITMQ_URL
        self._pw = locator.RABBITMQ_PW
        self._username = username
        self._vhost = vhost
        self.process_message = process_message
        self.on_connection_open_client = on_open
        self.exchange = exchange
        self.exchange_type = exchange_type
        self.routing_key = routing_key
        self.sent_msg = {}
        self.heartbeat = 60
        self.queue_name = queue_name
        self.ssl = ssl
        self.port = (5671 if ssl else 5672)
        self.qos_prefetch = qos_prefetch
        self.mandatory_deliver = mandatory
        self.durable = durable
        self.REQUEUE_TIMEOUT = 10
        self.encryption = encryption
        self.secur_server = secur_server
        self.replayNonce = unpack('Q', os.urandom(8))[0]
        self.ssl_options = ssl_options
        self.frontend = frontend
        
        if(encryption):
            with open(PRIVATE_KEY_FILE, 'r') as f:
                privKey = RSA.importKey(f.read())
                self.signer = PKCS1_PSS.new(privKey)
            if(secur_server):
                self.clusterKey = read_cluster_key()

    def connect(self):
        while not self._closing:
            self.LOGGER.info('Connecting to %s', self._url)

            try:
                if(self.ssl_options):
                    credentials = pika.credentials.ExternalCredentials()
                else:
                    credentials = pika.PlainCredentials(self._username,
                            self._pw)
                parameters = pika.ConnectionParameters(
                    self._url,
                    self.port,
                    self._vhost,
                    credentials,
                    ssl=self.ssl,
                    ssl_options=self.ssl_options,
                    heartbeat_interval=self.heartbeat,
                    )

                sel_con = \
                    pika.adapters.tornado_connection.TornadoConnection(parameters,
                        self.on_connection_open,
                        stop_ioloop_on_close=False)

                if self.on_connection_open_client:
                    sel_con.add_on_open_callback(self.on_connection_open_client)
                return sel_con
            except:
                self.LOGGER.exception('Error connecting rabbitmq server at %s'
                         % self._url)
                time.sleep(5)
                pass

    def on_connection_closed(
        self,
        connection,
        reply_code,
        reply_text,
        ):
        self._channel = None
        self._pub_channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            self.LOGGER.warning('Connection closed, reopening in 5 seconds: (%s) %s'
                                , reply_code, reply_text)
            self._connection.add_timeout(5, self.reconnect)

    def on_connection_open(self, unused_connection):
        self.LOGGER.info('Connection opened')
        self._connection.add_on_close_callback(self.on_connection_closed)

        self.LOGGER.info('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)
        self._connection.channel(on_open_callback=self.on_pub_channel_open)

    def reconnect(self):
        """Will be invoked by the IOLoop timer if the connection is
        closed. See the on_connection_closed method.

        """

        if not self._closing:

            # Create a new connection

            self._connection = self.connect()

    def on_channel_closed(
        self,
        channel,
        reply_code,
        reply_text,
        ):
        self.LOGGER.warning('Channel %i was closed: (%s) %s', channel,
                            reply_code, reply_text)
        self._connection.close()

        # for some reasons (which I don't have time to look at) it does not
        # call the call back on_connection_close when we stop so we need to
        # do it manually

        if self._closing:
            self._connection.ioloop.stop()

    def on_channel_open(self, channel):
        self.LOGGER.info('Channel opened')
        self._channel = channel
        self._channel.add_on_close_callback(self.on_channel_closed)
        if self.qos_prefetch:
            self._channel.basic_qos(prefetch_count=self.qos_prefetch)

        self.LOGGER.info('Declaring exchanges %s', self.exchange)
        if(self.encryption):
            self._channel.exchange_declare(self.on_key_exchange_declareok,
                    'keyexchange')
        
        if(not self.encryption or self.secur_server):
            self._channel.exchange_declare(self.on_exchange_declareok,
                    self.exchange, self.exchange_type, durable=self.durable)

    def on_pub_channel_open(self, channel):
        self._pub_channel = channel
        self._pub_channel.add_on_return_callback(self.on_return_callback)

    def on_exchange_declareok(self, unused_frame):
        self.LOGGER.info('Exchange declared')
        self.LOGGER.info('Declaring queue')
        self._channel.queue_declare(self.on_queue_declareok,
                                    queue=self.queue_name,
                                    auto_delete=self.queue_name == '',
                                    exclusive=self.queue_name == '',
                                    durable=self.durable
                                    )

    def on_key_exchange_declareok(self, unused_frame):
        self._channel.queue_declare(self.on_key_queue_declareok,
                                    queue='',
                                    auto_delete=True,
                                    exclusive=True,
                                    durable=True
                                    )

    def on_queue_declareok(self, method_frame):
        self.QUEUE = method_frame.method.queue

        self.LOGGER.info('Binding %s to %s with %s', self.exchange,
                         self.QUEUE, self.routing_key)
        self._channel.queue_bind(self.on_bindok, self.QUEUE,
                                 self.exchange, self.routing_key)

    def on_key_queue_declareok(self, method_frame):
        self.KEY_QUEUE = method_frame.method.queue
        self._channel.queue_bind(self.on_key_bindok, self.KEY_QUEUE,
                                 'keyexchange',
                                 ("key_request" if self.secur_server else self.routing_key))

    def on_consumer_cancelled(self, method_frame):
        """Invoked by pika when RabbitMQ sends a Basic.Cancel for a consumer
        receiving messages.
        """

        self.LOGGER.info('Consumer was cancelled remotely, shutting down: %r'
                         , method_frame)
        if self._channel:
            self._channel.close()

    def on_return_callback(self,  _channel, method, properties, body):
        """Method is called when message can't be delivered
        """

        if properties.message_id in self.sent_msg.keys():
            self.sent_msg.pop(properties.message_id)()
        else:
            self.LOGGER.error("Couldn't deliver message %s %s: host is not available"%(properties, body))

    def publish_message(
        self,
        message,
        routing_key=None,
        reply_to=None,
        exchange=None,
        correlation_id=None,
        on_fail=None,
        type=None,
        delivery_mode=1
        ):

        if exchange is None:
            exchange = self.exchange

        expiration = None if not self.encryption else MSG_TTL
        properties = pika.BasicProperties(app_id='rocks.RabbitMQClient'
                , reply_to=reply_to, message_id=str(self.replayNonce),
                correlation_id=correlation_id, type=type, delivery_mode=delivery_mode,
                timestamp = time.time(), expiration=expiration)

        if(self.encryption):
            
            if(not properties.reply_to):
                properties.reply_to = self.routing_key

            message = clusterEncrypt(self.clusterKey, message)

            digest = digestMessage(message, properties)

            sig = self.signer.sign(digest)

            properties.headers = dict(signature = b64encode(sig))


        self._pub_channel.basic_publish(exchange, routing_key, message,
                properties, mandatory=self.mandatory_deliver)
        if on_fail:
            self.sent_msg[properties.message_id] = on_fail
        self.LOGGER.info('Published message %s %s %s' % (message,
                         exchange, routing_key))
        self.replayNonce += 1

    def on_message(
        self,
        unused_channel,
        basic_deliver,
        properties,
        body,
        ):
        self.LOGGER.info('Received message # %s from %s: %s',
                         basic_deliver.delivery_tag, properties.app_id,
                         body)
        if properties.correlation_id and properties.correlation_id \
            in self.sent_msg.keys():
            del self.sent_msg[properties.correlation_id]

        ret = None
        if self.process_message:
            if(self.encryption):
                ciphertext = verifyMessage(body, properties, frontend=self.frontend)
                if(ciphertext is None):
                    self.LOGGER.error("Message verification failed")
                    return

                body = clusterDecrypt(self.clusterKey, body)
            ret = self.process_message(properties, body, basic_deliver)

        if ret == False:
            self._connection.add_timeout(self.REQUEUE_TIMEOUT, lambda : \
                    self._channel.basic_nack(basic_deliver.delivery_tag))
            self.LOGGER.debug('Nacked message %s'
                              % basic_deliver.delivery_tag)
        else:
            self._channel.basic_ack(basic_deliver.delivery_tag)

    def on_key_message(
        self,
        unused_channel,
        basic_deliver,
        properties,
        body,
        ):
        self.LOGGER.info('Received message # %s from %s: %s',
                         basic_deliver.delivery_tag, properties.app_id,
                         body)

        ciphertext = verifyMessage(body, properties)
        if(ciphertext is None):
            self.LOGGER.error("Message verification failed")
            return

        if(self.secur_server and properties.type == 'key_request'):
            msg = RsaEncrypt(dstHost=properties.reply_to, msg=self.clusterKey)

            send_properties = pika.BasicProperties(app_id='rocks.RabbitMQClient'
                , reply_to=self.routing_key, message_id=str(self.replayNonce),
                type="key_response", delivery_mode=2,
                timestamp = time.time(), expiration=MSG_TTL)

            digest = digestMessage(msg, send_properties)
            sig = self.signer.sign(digest)
            send_properties.headers = dict(signature = b64encode(sig))

            self._pub_channel.basic_publish("keyexchange", properties.reply_to, msg,
                send_properties)

            self.replayNonce += 1
        elif(not self.secur_server and properties.type == 'key_response'):
            if(properties.reply_to != self.frontend):
                self.LOGGER.error("Not getting keys from hosts other than frontend, %s != %s"%(self.frontend, properties.reply_to))
                return

            self.clusterKey = RsaDecrypt(ciphertext)
            self.LOGGER.debug("Got cluster key %s, initing regular queues"%self.clusterKey)
            self._channel.exchange_declare(self.on_exchange_declareok,
                    self.exchange, self.exchange_type, durable=self.durable)

    def on_cancelok(self, unused_frame):
        self.LOGGER.info('RabbitMQ acknowledged the cancellation of the consumer. Closing the channel')
        self._channel.close()

    def on_bindok(self, unused_frame):
        self.LOGGER.info('Queue bound')

        self.LOGGER.info('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

        self._consumer_tag = \
            self._channel.basic_consume(self.on_message, self.QUEUE)

    def on_key_bindok(self, unused_frame):
        self._key_consumer_tag = \
            self._channel.basic_consume(self.on_key_message, self.KEY_QUEUE, no_ack=True)
        if(not self.secur_server):
            message = json.dumps({"msg":"Gimme da key"})

            properties = pika.BasicProperties(app_id='rocks.RabbitMQClient'
                , reply_to=self.routing_key, message_id=str(self.replayNonce),
                type="key_request", delivery_mode=2,
                timestamp = time.time(), expiration=MSG_TTL)

            digest = digestMessage(message, properties)
            sig = self.signer.sign(digest)
            properties.headers = dict(signature = b64encode(sig))

            self._pub_channel.basic_publish("keyexchange", "key_request", message,
                properties)

            self.replayNonce += 1

    def run(self):
        self.LOGGER.info('starting ioloop')
        self._connection = self.connect()
        self._connection.ioloop.start()

    def stop(self):
        self.LOGGER.info('Stopping')
        self._closing = True
        if self._channel:
            self.LOGGER.info('Sending a Basic.Cancel RPC command to RabbitMQ'
                             )
            if(self._key_consumer_tag):
                self._channel.basic_cancel(
                        consumer_tag=self._key_consumer_tag)
            if(self._consumer_tag):
                self._channel.basic_cancel(callback=self.on_cancelok,
                        consumer_tag=self._consumer_tag)

        # for some reason the tornado ioloop does not get stopped when hit
        # by a SIGTERM, so we don't need to re-start it here
        # self._connection.ioloop.start()

        self.LOGGER.info('Stopped')
