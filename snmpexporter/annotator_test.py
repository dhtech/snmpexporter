import binascii
import collections
import unittest
import yaml

from snmpexporter import config
from snmpexporter import annotator
from snmpexporter import snmp


MIB_RESOLVER = {
    '.1.2.3': 'testInteger1',
    '.1.2.4': 'testInteger2',
    '.1.2.5': 'testInteger3',
    '.10.1': 'interfaceString',
    '.10.2': 'aliasString',
    '.10.3': 'enumString'
}

ENUMS = collections.defaultdict(dict)
ENUMS['.10.3'] = {'10': 'enumValue'}


def snmpResult(x, type=None):
  # We don't care about the type in the annotator
  if type is None:
    type = 'INTEGER' if isinstance(x, int) else 'OCTETSTR'
  return snmp.ResultTuple(str(x), type)


class MockMibResolver(object):

  def resolve_for_testing(self, oid):
    for key in MIB_RESOLVER:
      if oid.startswith(key + '.'):
        break
    else:
      raise Exception('No MIB RESOLVER defined')

    index = oid[len(key)+1:]
    return ('DUMMY-MIB', MIB_RESOLVER[key], index, ENUMS[key])

  def resolve(self, oid):
    mib, obj, index, enum = self.resolve_for_testing(oid)
    return '%s::%s.%s' % (mib, obj, index), enum


class TestAnnotator(unittest.TestCase):

  def setUp(self):
    self.mibresolver = MockMibResolver()

  def runTest(self, expected_entries, result, cfg):
    logic = annotator.Annotator(
      config=config.Config(cfg),
      mibresolver=self.mibresolver)
    expected_output = expected_entries
    output = logic.annotate(result)
    if output != expected_output:
      print('Output is not as expected!')
      print('Output:')
      for oid, v in output.results.items():
        print((oid, v))
      print('Expected:')
      for oid, v in expected_output.results.items():
        print((oid, v))
    self.assertEqual(output, expected_output)

  def createResultEntry(self, key, result, labels):
    # mib/objs etc. is tested in testResult so we can assume they are correct
    oid, ctxt = key
    mib, obj, index, _ = self.mibresolver.resolve_for_testing(oid)
    if not ctxt is None:
      labels = dict(labels)
      labels['vlan'] = ctxt
    return {key: annotator.AnnotatedResultEntry(
      result[key], mib, obj, index, labels)}

  def newExpectedFromResult(self, result):
    # We will most likely just pass through a lot of the results, so create
    # the basic annotated entries and just operate on the edge cases we are
    # testing.
    expected = {}
    for (key, ctxt), value in result.items():
      expected.update(self.createResultEntry((key, ctxt), result, {}))
    return expected

  def testSmokeTest(self):
    """Test empty config and empty SNMP result."""
    result = {}
    expected = {}
    self.runTest(expected, result, '')

  def testResult(self):
    """Test that results are propagated as we want."""
    result = {
      ('.1.2.4.1', '100'): snmpResult(1337)
    }
    # NOTE(bluecmd): Do *not* use createResultEntry here to make sure the
    # assumptions we're doing in that function are holding.
    expected = {
      ('.1.2.4.1', '100'): annotator.AnnotatedResultEntry(
        data=snmpResult(1337), mib='DUMMY-MIB', obj='testInteger2',
        index='1', labels={'vlan': '100'})
    }
    self.runTest(expected, result, '')

  def testSimpleAnnotation(self):
    """Test simple annotation and VLAN support."""
    config = """
annotator:
  annotations:
    - annotate:
        - .1.2
      with:
        interface: .10.1
        alias: .10.2
        nonexistant: .10.3
"""
    result = {
      ('.1.2.3.1', None): snmpResult(1337),
      ('.1.2.3.3', None): snmpResult(1338),
      ('.1.2.4.1', None): snmpResult(1339),
      ('.1.2.4.3.2', None): snmpResult(1340),
      ('.1.2.4.3.3', None): snmpResult(1341),
      ('.1.2.4.1', '100'): snmpResult(1339),
      ('.10.1.1', None): snmpResult('interface1'),
      ('.10.1.3.2', None): snmpResult('interface2'),
      ('.10.1.3.3', None): snmpResult('interface3'),
      ('.10.2.1', None): snmpResult('alias1'),
      ('.10.2.3.2', None): snmpResult('alias2'),
    }
    expected = self.newExpectedFromResult(result)
    expected.update(self.createResultEntry(('.1.2.3.1', None), result,
      {'interface': 'interface1', 'alias': 'alias1'}))
    expected.update(self.createResultEntry(('.1.2.4.1', None), result,
      {'interface': 'interface1', 'alias': 'alias1'}))
    expected.update(self.createResultEntry(('.1.2.4.3.2', None), result,
      {'interface': 'interface2', 'alias': 'alias2'}))
    expected.update(self.createResultEntry(('.1.2.4.1', '100'), result,
      {'interface': 'interface1', 'alias': 'alias1'}))
    expected.update(self.createResultEntry(('.1.2.4.3.3', None), result,
      {'interface': 'interface3'}))
    self.runTest(expected, result, config)

  def testSimpleAnnotationDeepLevel(self):
    """Test simple annotation and VLAN support."""
    config = """
annotator:
  annotations:
    - annotate:
        - .1.2[1]
      with:
        interface: .10.1
        alias: .10.2
"""
    result = {
      ('.1.2.3.1.666', None): snmpResult(1337),
      ('.1.2.3.3.666', None): snmpResult(1338),
      ('.1.2.4.1.666', None): snmpResult(1339),
      ('.1.2.4.1.666', '100'): snmpResult(1339),
      ('.10.1.1', None): snmpResult('interface1'),
      ('.10.1.3.2', None): snmpResult('interface2'),
      ('.10.2.1', None): snmpResult('alias1'),
      ('.10.2.3.2', None): snmpResult('alias2'),
    }
    expected = self.newExpectedFromResult(result)
    expected.update(self.createResultEntry(('.1.2.3.1.666', None), result,
      {'interface': 'interface1', 'alias': 'alias1'}))
    expected.update(self.createResultEntry(('.1.2.4.1.666', None), result,
      {'interface': 'interface1', 'alias': 'alias1'}))
    expected.update(self.createResultEntry(('.1.2.4.1.666', '100'), result,
      {'interface': 'interface1', 'alias': 'alias1'}))
    self.runTest(expected, result, config)

  def testSimpleAnnotationMultiDeepLevel(self):
    """Test simple annotation and VLAN support."""
    config = """
annotator:
  annotations:
    - annotate:
        - .1.2[1]
      with:
        interface: .10.1
        alias: .10.2
"""
    result = {
      ('.1.2.3.1.1.666', None): snmpResult(1337),
      ('.1.2.3.1.3.666', None): snmpResult(1338),
      ('.1.2.4.1.1.666', None): snmpResult(1339),
      ('.1.2.4.1.1.666', '100'): snmpResult(1339),
      ('.10.1.1.1', None): snmpResult('interface1'),
      ('.10.1.3.1.2', None): snmpResult('interface2'),
      ('.10.2.1.1', None): snmpResult('alias1'),
      ('.10.2.3.1.2', None): snmpResult('alias2'),
    }
    expected = self.newExpectedFromResult(result)
    expected.update(self.createResultEntry(('.1.2.3.1.1.666', None), result,
      {'interface': 'interface1', 'alias': 'alias1'}))
    expected.update(self.createResultEntry(('.1.2.4.1.1.666', None), result,
      {'interface': 'interface1', 'alias': 'alias1'}))
    expected.update(self.createResultEntry(('.1.2.4.1.1.666', '100'), result,
      {'interface': 'interface1', 'alias': 'alias1'}))
    self.runTest(expected, result, config)

  def testMultiLevelAnnotation(self):
    """Test multi level annotation."""
    config = """
annotator:
  annotations:
    - annotate:
        - .1.2.3
      with:
        interface: .1.2.4 > .1.2.5 > .10.1
"""
    result = {
      ('.1.2.3.1', None): snmpResult(1337),
      ('.1.2.4.1', None): snmpResult(5),
      ('.1.2.5.5', None): snmpResult(3),
      ('.10.1.3', None): snmpResult('correct'),
    }
    expected = self.newExpectedFromResult(result)
    expected.update(self.createResultEntry(('.1.2.3.1', None), result,
      {'interface': 'correct'}))
    self.runTest(expected, result, config)

  def testMultiLevelAnnotationValue(self):
    """Test multi level annotation via value."""
    config = """
annotator:
  annotations:
    - annotate:
        - .1.2.3
      with:
        interface: $.1.2.4 > .1.2.5 > .10.1
"""
    result = {
      ('.1.2.3.1337', None): snmpResult(1),
      ('.1.2.4.1', None): snmpResult(5),
      ('.1.2.5.5', None): snmpResult(3),
      ('.10.1.3', None): snmpResult('correct'),
    }
    expected = self.newExpectedFromResult(result)
    expected.update(self.createResultEntry(('.1.2.3.1337', None), result,
      {'interface': 'correct'}))
    self.runTest(expected, result, config)

  def testMultiLevelAnnotationContext(self):
    """Test multi level annotation across contexts."""
    config = """
annotator:
  annotations:
    - annotate:
        - .1.2.3
      with:
        interface: .1.2.4 > .1.2.5 > .10.1
"""
    result = {
      ('.1.2.3.1', '100'): snmpResult(1337),
      ('.1.2.4.1', '100'): snmpResult(5),
      ('.1.2.5.5', None): snmpResult(3),
      ('.10.1.3', None): snmpResult('correct'),
    }
    expected = self.newExpectedFromResult(result)
    expected.update(self.createResultEntry(('.1.2.3.1', '100'), result,
      {'interface': 'correct'}))
    self.runTest(expected, result, config)

  def testMultiLevelAnnotationBroken(self):
    """Test multi level annotation where we do not have a match."""
    config = """
annotator:
  annotations:
    - annotate:
        - .1.2.3
      with:
        interface: .1.2.4 > .1.2.5 > .10.1
"""
    result = {
      ('.1.2.3.1', '100'): snmpResult(1337),
      ('.1.2.4.1', '100'): snmpResult(6),
      ('.1.2.5.5', None): snmpResult(3),
      ('.10.1.3', None): snmpResult('dummy'),
    }
    expected = self.newExpectedFromResult(result)
    self.runTest(expected, result, config)

  def testMultiLevelAnnotationNonExistant(self):
    """Test multi level annotation where we didn't scrape the OID."""
    config = """
annotator:
  annotations:
    - annotate:
        - .1.2.3
      with:
        interface: .1.2.4 > .1.2.6 > .10.1
"""
    result = {
      ('.1.2.3.1', '100'): snmpResult(1337),
      ('.1.2.4.1', '100'): snmpResult(5),
      ('.1.2.5.5', None): snmpResult(3),
      ('.10.1.3', None): snmpResult('dummy'),
    }
    expected = self.newExpectedFromResult(result)
    self.runTest(expected, result, config)

  def testLabelify(self):
    """Test conversion of strings to values."""
    config = """
annotator:
  labelify:
    - .10.2
"""
    result = {
      ('.10.2.1', None): snmpResult('correct'),
      ('.10.2.2', None): snmpResult('\xffabc\xff '),
      ('.10.2.3', None): snmpResult(''),
      ('.10.2.4', None): snmpResult(2),
    }
    identities = {
      ('.10.2.1', None): snmpResult('NaN', 'ANNOTATED'),
      ('.10.2.2', None): snmpResult('NaN', 'ANNOTATED'),
    }
    expected = self.newExpectedFromResult(result)
    expected.update(self.createResultEntry(('.10.2.1', None), identities,
      {'value': 'correct', 'hex': binascii.hexlify('correct'.encode())}))
    expected.update(self.createResultEntry(('.10.2.2', None), identities,
      {'value': 'abc', 'hex': binascii.hexlify('\xffabc\xff '.encode())}))
    # Empty strings should not be included
    del expected[('.10.2.3', None)]
    # Only strings are labelified
    del expected[('.10.2.4', None)]
    self.runTest(expected, result, config)

  def testEnums(self):
    """Test conversion of enums to values."""
    result = {
      ('.10.3.1', None): snmpResult(10),
    }
    expected = self.newExpectedFromResult(result)
    expected.update(self.createResultEntry(('.10.3.1', None), result,
      {'enum': 'enumValue'}))
    self.runTest(expected, result, '')

  def testEnumsInvalid(self):
    """Test conversion of enums to values (invalid value)."""
    result = {
      ('.10.3.1', None): snmpResult(9),
    }
    expected = self.newExpectedFromResult(result)
    self.runTest(expected, result, '')

  def testEnumsAnnotation(self):
    """Test conversion of enums to values in annotations."""
    config = """
annotator:
  annotations:
    - annotate:
        - .1.2.3
      with:
        thing: .10.3
"""

    result = {
      ('.1.2.3.1', None): snmpResult(10),
      ('.10.3.1', None): snmpResult(10),
    }
    expected = self.newExpectedFromResult(result)
    expected.update(self.createResultEntry(('.1.2.3.1', None), result,
      {'thing': 'enumValue'}))
    expected.update(self.createResultEntry(('.10.3.1', None), result,
      {'enum': 'enumValue'}))
    self.runTest(expected, result, config)


def main():
  unittest.main()


if __name__ == '__main__':
  main()
