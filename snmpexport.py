#!/usr/bin/env python3
import argparse

import snmpexporter.config
import snmpexporter.target
import snmpexporter.poller
import snmpexporter.snmpimpl
import snmpexporter.annotator


def main(config_file, host, layer):
  with open(config_file, 'r') as f:
    config = snmpexporter.config.Config(f.read())
  # TODO(bluecmd): fix
  mibresolver = None
  snmpimpl = snmpexporter.snmpimpl.NetsnmpImpl()
  target = snmpexporter.target.SnmpTarget(host, layer, config)
  poller = snmpexporter.poller.Poller(config)
  annotator = snmpexporter.annotator.Annotator(config, mibresolver)

  for result in annotator.annotate(poller.poll(target)):
    print(result)


if __name__ == '__main__':
  import argparse

  parser = argparse.ArgumentParser(description='One-shot SNMP exporter.')
  parser.add_argument('--config', dest='config_file', type=str,
          help='config file to load', default='/etc/snmpexporter.yaml')
  parser.add_argument('host', type=str, help='host to scrape')
  parser.add_argument('layer', type=str, help='layer to use for authentication')
  args = parser.parse_args()
  main(args.config_file, args.host, args.layer)
