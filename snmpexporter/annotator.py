#!/usr/bin/env python3
import binascii
import collections
import logging

from snmpexporter import snmp


AnnotatedResultEntry = collections.namedtuple('AnnotatedResultEntry',
  ('data', 'mib', 'obj', 'index', 'labels'))


class Annotator(object):
  """Annotation step where results are given meaningful labels."""

  LABEL_TYPES = set(['OCTETSTR', 'IPADDR'])
  ALLOWED_CHARACTERS = (
    '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ ')

  def __init__(self, config, mibresolver):
    super(Annotator, self).__init__()
    self.config = config
    self.mibresolver = mibresolver

  def annotate(self, results):
    annotations = self.config.get('annotations', [])

    # Calculate map to skip annotation if we're sure we're not going to annotate
    # TODO(bluecmd): This could be cached
    annotation_map = {}
    for annotation in annotations:
      for annotate in annotation['annotate']:
        # Support for processing the index (for OIDs that have X.Y where we're
        # interested in joining on X)
        if '[' in annotate:
          annotate, offset = annotate.split('[', 1)
          offset = int(offset.strip(']'))
        else:
          offset = None
        # Add '.' to not match .1.2.3 if we want to annotate 1.2.30
        annotation_map[(annotate + '.', offset)] = annotation['with']

    labelification = set(
      [x + '.' for x in self.config.get('labelify', [])])

    # Pre-fill the OID/Enum cache to allow annotations to get enum values
    mibcache = dict()
    for (oid, ctxt), result in results.items():
      resolve = self.mibresolver.resolve(oid)
      mibcache[oid] = resolve
      if resolve is None:
        logging.warning('Failed to look up OID %s, ignoring', oid)
        continue

    # Calculate annotator map
    split_oid_map = collections.defaultdict(dict)
    for (oid, ctxt), result in results.items():
      resolve = mibcache.get(oid, None)
      if resolve is None:
        continue
      name, _ = resolve

      _, index = name.split('.', 1)
      key = oid[:-(len(index))]
      split_oid_map[(key, ctxt)][index] = result.value

    annotated_results = {}
    for (oid, ctxt), result in results.items():
      resolve = mibcache.get(oid, None)
      if resolve is None:
        continue

      labels = {}
      vlan = None

      # TODO(bluecmd): If we support more contexts we need to be smarter here
      if not ctxt is None:
        vlan = ctxt

      name, enum = resolve

      if not '::' in name:
        logging.warning('OID %s resolved to %s (no MIB), ignoring', oid, name)
        continue

      mib, part = name.split('::', 1)
      obj, index = part.split('.', 1) if '.' in part else (part, None)

      labels = {}
      if not vlan is None:
        labels['vlan'] = vlan
      labels.update(
        self.annotated_join(
          oid, index, ctxt, annotation_map, split_oid_map, results))

      # Handle labelification
      if oid[:-len(index)] in labelification:
        # Skip empty strings or non-strings that are up for labelification
        if result.value == '' or result.type not in self.LABEL_TYPES:
          continue
        labels['value'] = self.string_to_label_value(result.value)
        labels['hex'] = binascii.hexlify(result.value.encode())
        result = snmp.ResultTuple('NaN', 'ANNOTATED')

      # Do something almost like labelification for enums
      if enum:
        enum_value = enum.get(result.value, None)
        if enum_value is None:
          logging.warning('Got invalid enum value for %s (%s), not labling',
            oid, result.value)
        else:
          labels['enum'] = enum_value

      annotated_results[(oid, vlan)] = AnnotatedResultEntry(
        result, mib, obj, index, labels)

    logging.debug('Annotation completed for %d metrics', len(annotated_results))
    return annotated_results

  def annotated_join(self, oid, index, ctxt, annotation_map, split_oid_map,
                     results):
    for key, offset in annotation_map:
      if oid.startswith(key):
        break
    else:
      return {}

    if offset is not None:
      index_parts = index.split('.')
      index = '.'.join(index_parts[:-offset])
    labels = {}
    for label, annotation_path in annotation_map[(key, offset)].items():
      # Parse the annotation path
      annotation_keys = [x.strip() + '.' for x in annotation_path.split('>')]

      value = self.jump_to_value(
        annotation_keys, oid, ctxt, index, split_oid_map, results)
      if value is None:
        continue

      labels[label] = value.replace('"', '\\"')
    return labels

  def jump_to_value(self, keys, oid, ctxt, index, split_oid_map, results):
    # Jump across the path seperated like:
    # OID.idx:value1
    # OID2.value1:value2
    # OID3.value3:final
    # label=final
    for key in keys:
      use_value = key[0] == '$'
      if use_value:
        key = key[1:]

      # Try to associate with context first
      part = split_oid_map.get((key, ctxt), None)
      if not part:
        # Fall back to the global context
        part = split_oid_map.get((key, None), None)
        # Do not allow going back into context when you have jumped into
        # the global one.
        # TODO(bluecmd): I have no reason *not* to support this more than
        # it feels like an odd behaviour and not something I would be
        # expecting the software to do, so let's not do that unless we find
        # a usecase in the future.
        ctxt = None
        if not part:
          return None

      # We either use the last index or the OID value, deterimed by
      # use_value above.
      if use_value:
        index = results[(oid, ctxt)].value

      oid = ''.join((key, index))
      index = part.get(index, None)
      if not index:
        return None

    value = results[(oid, ctxt)].value

    # Try enum resolution
    _, enum = mibcache[oid]
    if enum:
      enum_value = enum.get(value, None)
      if enum_value is None:
        logging.warning('Got invalid enum value for %s (%s), ignoring',
          oid, value)
        return None
      value = enum_value
    return value

  def string_to_label_value(self, value):
    value = ''.join(x for x in value.strip() if x in self.ALLOWED_CHARACTERS)
    return value.strip()
