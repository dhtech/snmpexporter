#!/usr/bin/env python3
import argparse
import logging
import sys
import yaml

import snmpexporter

def main(config_file, host, layer, annotate=True):
  with open(config_file, 'r') as f:
    config = yaml.safe_load(f.read())
  collections = config['collection']
  overrides = config['override']
  snmp_creds = config['snmp']
  annotator_config = config['annotator']

  if not annotate:
    logging.debug('Will not annotate')

  resolver = snmpexporter.ForkedResolver()

  logging.debug('Initializing Net-SNMP implemention')
  snmpimpl = snmpexporter.snmpimpl.NetsnmpImpl()

  results = snmpexporter.probe(
    host, layer, collections, overrides, snmp_creds, annotator_config,
    resolver, snmpimpl, annotate)

  for (oid, vlan), value in sorted(results.items()):
    print(str(vlan if vlan else '').ljust(5), oid.ljust(50), value)


if __name__ == '__main__':
  import argparse

  parser = argparse.ArgumentParser(description='One-shot SNMP exporter.')
  parser.add_argument('--config', dest='config_file', type=str,
          help='config file to load', default='/etc/snmpexporter.yaml')
  parser.add_argument('--log-level', dest='log_level', type=str,
          help='log level', default='INFO')
  parser.add_argument('--annotate', dest='annotate', default=False, const=True,
          help='annotate the results', action='store_const')
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

  main(args.config_file, args.host, args.layer, annotate=args.annotate)
