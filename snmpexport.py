#!/usr/bin/env python3
import argparse
import logging
import sys
import yaml

import snmpexporter.target
import snmpexporter.poller
import snmpexporter.snmpimpl
import snmpexporter.annotator


def main(config_file, host, layer):
  with open(config_file, 'r') as f:
    config = yaml.safe_load(f.read())
  collections = config['collection']
  overrides = config['override']
  snmp_creds = config['snmp']

  # TODO(bluecmd): fix
  mibresolver = None
  logging.debug('Initializing Net-SNMP implemention')
  snmpimpl = snmpexporter.snmpimpl.NetsnmpImpl()
  logging.debug('Constructing SNMP target')
  target = snmpexporter.target.SnmpTarget(host, layer, snmp_creds)
  logging.debug('Creating SNMP poller')
  poller = snmpexporter.poller.Poller(collections, overrides, snmpimpl)
  logging.debug('Creating result annotator')
  annotator = snmpexporter.annotator.Annotator(config, mibresolver)

  logging.debug('Starting poll')
  for result in annotator.annotate(poller.poll(target)):
    print(result)


if __name__ == '__main__':
  import argparse

  parser = argparse.ArgumentParser(description='One-shot SNMP exporter.')
  parser.add_argument('--config', dest='config_file', type=str,
          help='config file to load', default='/etc/snmpexporter.yaml')
  parser.add_argument('--log-level', dest='log_level', type=str,
          help='log level', default='INFO')
  parser.add_argument('host', type=str, help='host to scrape')
  parser.add_argument('layer', type=str, help='layer to use for authentication')
  args = parser.parse_args()

  # Logging setup
  root = logging.getLogger()
  ch = logging.StreamHandler(sys.stderr)
  formatter = logging.Formatter( '%(asctime)s - %(name)s - '
              '%(levelname)s - %(message)s' )
  ch.setFormatter(formatter)
  root.addHandler(ch)
  root.setLevel(logging.getLevelName(args.log_level))

  main(args.config_file, args.host, args.layer)
