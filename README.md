# SDSC "rabbitmq" roll

## Overview

This roll bundles rabbitmq.

For more information about the various packages included in the rabbitmq roll please visit their official web pages:

- <a href="" target="_blank"></a> is .
- <a href="" target="_blank"></a> is .


## Requirements

To build/install this roll you must have root access to a Rocks development
machine (e.g., a frontend or development appliance).

If your Rocks development machine does *not* have Internet access you must
download the appropriate rabbitmq source file(s) using a machine that does
have Internet access and copy them into the `src/<package>` directories on your
Rocks development machine.


## Dependencies

Unknown at this time.


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

To install, execute these instructions on a Rocks frontend:

```shell
% rocks add roll *.iso
% rocks enable roll rabbitmq
% cd /export/rocks/install
% rocks create distro
% rocks run roll rabbitmq | bash
```


