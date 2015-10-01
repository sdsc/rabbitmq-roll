#!/bin/bash

"""This script generates random passsword for given NAME and adds NAME user and vhost to rabbitmq"""                                                          

: ${1?"Usage: $0 name"}
NAME=$1
admin_pass=$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c26)
/usr/sbin/rabbitmqctl add_user $NAME ${admin_pass}
/usr/sbin/rabbitmqctl add_vhost $NAME
/usr/sbin/rabbitmqctl set_permissions -p $NAME $NAME ".*" ".*" ".*"
/usr/sbin/rabbitmqctl set_permissions -p $NAME admin ".*" ".*" ".*"
echo "${admin_pass}" > /opt/rocks/etc/rabbitmq_$NAME.conf
chmod 400 /opt/rocks/etc/rabbitmq_$NAME.conf
