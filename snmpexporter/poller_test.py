#!/usr/bin/env python3
"""Which OIDs a device is asked for, with the collection file as it is
shipped (etc/snmpexporter.yaml): the layer and the model decide."""
import os
import types
import unittest

from snmpexporter import config as config_file
from snmpexporter import poller

CONFIG = os.path.join(os.path.dirname(__file__), '..', 'etc', 'snmpexporter.yaml')
UPS_BATTERY = '.1.3.6.1.2.1.33.1.2'
UPS_ALARM = '.1.3.6.1.2.1.33.1.6'
XUPS_ENVIRONMENT = '.1.3.6.1.4.1.534.1.6'
RACK_INFO = '.1.3.6.1.4.1.232.22'
FRU_NAME = '.1.3.6.1.4.1.2636.3.1.15.1.5'
FRU_STATE = '.1.3.6.1.4.1.2636.3.1.15.1.8'
SYS_UPTIME = '.1.3.6.1.2.1.1.3'


def oids_for(layer, model):
  config = config_file.load(CONFIG)
  p = poller.Poller(config['collection'], config.get('override'), None)
  # the choice of OIDs reads only the device's layer
  t = types.SimpleNamespace(host='device.example.net', layer=layer)
  oids, vlan_aware, _ = p.assemble_walk_parameters(t, model)
  return set(oids) | set(vlan_aware)


class TestCollection(unittest.TestCase):

  def testUpsCardIsAskedForUpsValues(self):
    # the card names itself freely: any model of the layer is a UPS
    for model in ('Gigabit Network Card 3', 'Rack 4 UPS', ''):
      oids = oids_for('services', model)
      self.assertIn(UPS_BATTERY, oids)
      # the alarm GROUP: a walk of upsAlarmsPresent's own OID (.6.1)
      # returns nothing with this walker
      self.assertIn(UPS_ALARM, oids)
      self.assertNotIn(UPS_ALARM + '.1', oids)
      self.assertIn(XUPS_ENVIRONMENT, oids)
      self.assertIn(SYS_UPTIME, oids)

  def testUpsValuesAreForTheServicesLayerOnly(self):
    for layer in ('access', 'dist', 'core', 'wifi', 'firewall'):
      for model in ('Gigabit Network Card 3', 'WS-C2960X-48LPD-L', 'ex3400-24t'):
        oids = oids_for(layer, model)
        self.assertNotIn(UPS_BATTERY, oids, (layer, model))
        self.assertNotIn(XUPS_ENVIRONMENT, oids, (layer, model))

  def testOtherServicesCollectionStillNeedsItsModel(self):
    self.assertNotIn(RACK_INFO, oids_for('services', 'Gigabit Network Card 3'))
    self.assertIn(RACK_INFO, oids_for('services', 'HP Onboard Administrator c7000'))

  def testJuniperSwitchAndRouterAreAskedForFruState(self):
    # the state of power supplies and fans, with the name to label it by
    for layer in ('access', 'dist', 'core'):
      for model in ('Juniper Networks, Inc. ex4300-24t Ethernet Switch',
                    'Juniper Networks, Inc. qfx5120-48y Ethernet Switch',
                    'Juniper Networks, Inc. MX204 Edge Router',
                    '750-000000'):
        oids = oids_for(layer, model)
        self.assertIn(FRU_STATE, oids, (layer, model))
        self.assertIn(FRU_NAME, oids, (layer, model))

  def testFruStateIsForJuniperSwitchAndRouterOnly(self):
    for model in ('WS-C2960X-48LPD-L', 'Gigabit Network Card 3',
                  'Juniper Networks, Inc. srx300 internet router',
                  '710-000000'):
      for layer in ('access', 'dist', 'core', 'firewall', 'services'):
        self.assertNotIn(FRU_STATE, oids_for(layer, model), (layer, model))


if __name__ == '__main__':
  unittest.main()
