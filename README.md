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

## Installation

You can either install it directly or use Docker/Kubernetes to run the exporter.

See Dockerfile for instructions on what dependencies are needed.
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
