# SDSC "rabbitmq" roll

## Overview

This roll bundles AMQP RabbitMQ server and Pika client library, with python helper package implementing a linux daemon listening to an AMQP queue.

For more information about the various packages included in the rabbitmq roll please visit their official web pages:

- <a href="http://www.rabbitmq.com/" target="_blank">http://www.rabbitmq.com/</a> - RabbitMQ homepage
- <a href="http://pika.readthedocs.org/">http://pika.readthedocs.org/</a> - pika client library


## Requirements

To build/install this roll you must have root access to a Rocks development
machine (e.g., a frontend or development appliance).

If your Rocks development machine does *not* have Internet access you must
download the appropriate rabbitmq source file(s) using a machine that does
have Internet access and copy them into the `src/<package>` directories on your
Rocks development machine.


## Dependencies

Included in the roll:
- backports.ssl_match_hostname python package
- tornado python package


## Building

To build the rabbitmq-roll, execute these instructions on a Rocks development
machine (e.g., a frontend or development appliance):

```shell
% make default 2>&1 | tee build.log
% grep "RPM build error" build.log
```

If nothing is returned from the grep command then the roll should have been
created as... `rabbitmq-*.iso`. If you built the roll on a Rocks frontend then
proceed to the installation step. If you built the roll on a Rocks development
appliance you need to copy the roll to your Rocks frontend before continuing
with installation.


## Installation

The RabbitMQ server will be installed on a node having the RABBITMQ_Server attribute set up.

After the installation a script will be looking at /opt/rocks/etc waiting for rabbitmq_*.conf files to appear for an hour. Each such file should contain a random-generated password for its user/virtualhost which will be automatically added to RabbitMQ during this hour. The virtual host and user will be created and admin user will be given admin permissions for this virtual host. These files are expected to be on all nodes via 411 for applications to be able to communicate to the server.

Additionaly there will be /opt/rocks/etc/rabbitmq.conf file containing the hostname of the node having RabbitMQ server installed, also distributed via 411. The admin password will be stored in /opt/rocks/etc/rabbitmq-admin.conf file.

To install, execute these instructions on a Rocks frontend:

```shell
% rocks set host attr {host} RABBITMQ_Server True
% rocks add roll *.iso
% rocks enable roll rabbitmq
% cd /export/rocks/install
% rocks create distro
% rocks run roll rabbitmq | bash
```


