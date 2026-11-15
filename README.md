[![Build Status](https://travis-ci.org/dhtech/snmpexporter.svg?branch=master)](https://travis-ci.org/dhtech/snmpexporter)
[![Coverage Status](https://coveralls.io/repos/github/dhtech/snmpexporter/badge.svg?branch=master)](https://coveralls.io/github/dhtech/snmpexporter?branch=master)

snmpexporter
=====

SNMP Poller written for DreamHack.

This product was previously called snmpcollector when it was part of the bigger
monitoring system called "dhmon". It is nowadays fully standalone
and should have very few if any ties back to DreamHack.

## What it is

snmpexporter is a software that given a host that speaks SNMP will try to poll
it and mangle the data into something more suitable as metrics.

The core feature of the snmpexporter is its annotation feature where it can
join different SNMP OIDs together to create something better than what SNMP
already has today. It also supports MIBs.

## Why snmpexporter

Compared to the official Prometheus SNMP exporter, this exporter is more
flexible as it knows how to read MIBs. That's basically it. It has some
minor annotation features that might be useful, but nothing extraordinary.

## Debian package

A tag `vX.Y.Z` (the version in the file `VERSION`) makes CI build, try
and publish `snmpexporter_X.Y.Z_amd64.deb` on a GitHub release. It is
built on Debian 13 for Debian 13's own Python and Net-SNMP, so a server
that installs it needs no compiler:

```
apt install ./snmpexporter_X.Y.Z_amd64.deb
```

What is in it:

 * `/usr/sbin/snmpexporterd` and `/usr/bin/snmpexport`, the two programs
   (see Running), with their code, the compiled MIB resolver and the
   Net-SNMP Python module in `/usr/lib/snmpexporter`. The Python module
   is in no Debian package; it is a release of
   [our fork of python3-netsnmp](https://github.com/dhtech/python3-netsnmp),
   named and checksummed in `.github/build.sh`.
 * `snmpexporterd@.service`: one instance per port
   (`systemctl enable --now snmpexporterd@9190`), running as the account
   `snmpexporter`, which the package creates. Nothing is enabled or
   started by the installation.
 * `/etc/snmpexporter/snmpexporter.yaml`: what is collected from which
   model.

What it needs from you:

 * `/etc/snmpexporter/auth.yaml`: the credentials per layer (example in
   `/usr/share/doc/snmpexporter/examples/`), readable for the group
   `snmpexporter` only.
 * MIB files. The package holds none. `/etc/default/snmpexporter` says
   where they are (`MIBDIRS`, `MIBS`) and can add switches for the
   daemons (`SNMPEXPORTERD_OPTS`, e.g. `--address 127.0.0.1`); example in
   the same directory. `snmpexport` reads the same file, so a poll by
   hand resolves names as the daemons do.

`.github/build.sh` builds the package and `.github/try.sh` tries it: in
a container that has only the package, it polls Debian's `snmpd` over
SNMPv3 and SNMPv2c and checks the metrics that come back.

## Installation by hand

You can either install it directly or use Docker/Kubernetes to run the exporter.

See Dockerfile for instructions on what dependencies are needed. Something like this (may not be up to date, again - see Dockerfile):

```
sudo apt-get install libsnmp-dev python3-distutils python3-dev python3-coverage python3-yaml python3-objgraph python3-twisted python3-pip python3-setuptools python3-wheel
pip3 install python3-netsnmp

mkdir -p /var/lib/mibs/std /tmp/librenms
cd /tmp/librenms
wget https://github.com/librenms/librenms/archive/master.zip
unzip master.zip
mv librenms-master/mibs/* /var/lib/mibs/std/

cp etc/snmp.conf /etc/snmp/

make
make install
```

Run `make install` to install.

To deploy to Kubernetes, upload the Docker image to a repository and modify
`snmpexporterd.k8s.yaml`.

## Running

There are two applications in snmpexporter:

 * snmpexporterd.py
 
This is an API server capable of doing scrapes via HTTP requests.
This is an excellent way to integrate SNMP into Prometheus.
 
 * snmpexport.py

This is a utility script to test your configuration or debug SNMP polling
behaviour. Run it to execute a one-off scraping.
