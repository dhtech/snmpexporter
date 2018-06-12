#!/usr/bin/env python3
import argparse
import logging
import sys

import snmpexporter
import snmpexporter.config
import snmpexporter.prometheus


def main(config_file, host, layer, annotate=True):
  config = snmpexporter.config.load(config_file)
  collections = config['collection']
  overrides = config['override']
  snmp_creds = config['snmp']
  annotator_config = config['annotator']

  if not annotate:
    logging.debug('Will not annotate')

  resolver = snmpexporter.ForkedResolver()

  logging.debug('Initializing Net-SNMP implemention')
  snmpimpl = snmpexporter.snmpimpl.NetsnmpImpl()

  logging.debug('Constructing SNMP target')
  target = snmpexporter.target.SnmpTarget(host, layer, snmp_creds)

  target.start('poll')

  logging.debug('Creating SNMP poller')
  poller = snmpexporter.poller.Poller(collections, overrides, snmpimpl)

  logging.debug('Starting poll')
  data, timeouts, errors = poller.poll(target)
  target.add_timeouts(timeouts)
  target.add_errors(errors)

  if not annotate:
    for (oid, vlan), value in sorted(data.items()):
      print(str(vlan if vlan else '').ljust(5), oid.ljust(50), value)
    return

  target.start('annotate')

  logging.debug('Creating result annotator')
  annotator = snmpexporter.annotator.Annotator(annotator_config, resolver)

  logging.debug('Starting annotation')
  data = annotator.annotate(data)

  target.done()

  exporter = snmpexporter.prometheus.Exporter()
  for x in exporter.export(target, data):
    print(x)


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
