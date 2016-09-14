#!/usr/bin/env python3
import snmpexporter.config
import snmpexporter.target
import snmpexporter.poller
import snmpexporter.snmpimpl
import snmpexporter.annotator


def main(host, layer):
  with file('/etc/snmpexporter.yaml', 'r') as f:
    config = snmpexporter.config.Config(f.read())
  # TODO(bluecmd): fix
  mibresolver = None
  snmpimpl = snmpexporter.snmpimpl.NetsnmpImpl()
  target = snmpexporter.target.SnmpTarget(host, layer, config)
  poller = snmpexporter.poller.Poller(config)
  annotator = snmpexporter.annotator.Annotator(config, mibresolver)

  for result in annotator.annotate(poller.poll(target))):
    print(result)


if __name__ == '__main__':
  import sys
  main(*sys.argv[1:])
