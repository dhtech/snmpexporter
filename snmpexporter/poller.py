#!/usr/bin/env python2
import collections
import logging
import re

from snmpexporter import snmp


class Poller(object):

  def __init__(self, collections, overrides, snmpimpl):
    super(Poller, self).__init__()
    self.model_oid_cache = {}
    self.model_oid_cache_incarnation = 0
    self.snmpimpl = snmpimpl
    self.collections = collections
    self.overrides = overrides

  def assemble_walk_parameters(self, target, model):
    oids = set()
    vlan_aware_oids = set()
    options = dict()
    for collection_name, collection in self.collections.items():
      for regexp in collection['models']:
        options.update(collection.get('options', {}))
        layers = collection.get('layers', None)
        if layers and target.layer not in layers:
          continue
        if 'oids' in collection and re.match(regexp, model):
          logging.debug(
              'Model %s matches collection %s', model, collection_name)
          # VLAN aware collections are run against every VLAN.
          # We don't want to run all the other OIDs (there can be a *lot* of
          # VLANs).
          vlan_aware = collection.get('vlan_aware', False)
          if vlan_aware:
            vlan_aware_oids.update(set(collection['oids']))
          else:
            oids.update(set(collection['oids']))
    return (list(oids), list(vlan_aware_oids), options)

  def process_overrides(self, results):
    if not self.overrides:
      return results
    overridden_oids = set(self.overrides.keys())

    overriden_results = results
    for (oid, vlan), result in results.items():
      root = '.'.join(oid.split('.')[:-1])
      if root in overridden_oids:
        overriden_results[(oid, vlan)] = snmp.ResultTuple(
            result.value, self.overrides[root])
    return overriden_results

  def poll(self, target):
    results, errors, timeouts = self._walk(target)
    results = results if results else {}
    logging.debug('Done SNMP poll (%d objects) for "%s"',
        len(list(results.keys())), target.host)
    return results, timeouts, errors

  def _walk(self, target):
    try:
      model = self.snmpimpl.model(target)
    except snmp.TimeoutError as e:
      logging.exception('Could not determine model of %s:', target.host)
      return None, 0, 1
    except snmp.Error as e:
      logging.exception('Could not determine model of %s:', target.host)
      return None, 1, 0
    if not model:
      logging.error('Could not determine model of %s')
      return None, 1, 0

    logging.debug('Object %s is model %s', target.host, model)
    global_oids, vlan_oids, options = self.assemble_walk_parameters(
        target, model)

    # Apply walk options
    target.max_size = min(options.get('max-size'), target.max_size)
    logging.debug('Using max_size %d for %s', target.max_size, target.host)

    timeouts = 0
    errors = 0

    # 'None' is global (no VLAN aware)
    vlans = set([None])
    try:
      if vlan_oids:
        vlans.update(target.vlans())
    except snmp.Error as e:
      errors += 1
      logging.warning('Could not list VLANs: %s', str(e))

    to_poll = []
    for vlan in list(vlans):
      oids = vlan_oids if vlan else global_oids
      to_poll.append((target, vlan, oids))

    results = {}
    for part_results, part_errors, part_timeouts in map(self._poll, to_poll):
      results.update(self.process_overrides(part_results))
      errors += part_errors
      timeouts += part_timeouts
    return results, errors, timeouts

  def _poll(self, data):
    # TODO(bluecmd): Might want to have some sort of concurrency here
    # as experience tells me this can be slow to do for all VLANs.
    target, vlan, oids = data
    errors = 0
    timeouts = 0
    results = {}
    for oid in oids:
      logging.debug('Collecting %s on %s @ %s', oid, target.host, vlan)
      if not oid.startswith('.1'):
        logging.warning(
            'OID %s does not start with .1, please verify configuration', oid)
        continue
      try:
        results.update(
            {(k, vlan): v for k, v in self.snmpimpl.walk(
              target, oid, vlan).items()})
      except snmp.TimeoutError as e:
        timeouts += 1
        if vlan:
          logging.debug(
              'Timeout, is switch configured for VLAN SNMP context? %s', e)
        else:
          logging.debug('Timeout, slow switch? %s', e)
      except snmp.Error as e:
        errors += 1
        logging.warning('SNMP error for OID %s@%s: %s', oid, vlan, str(e))
    return results, errors, timeouts
