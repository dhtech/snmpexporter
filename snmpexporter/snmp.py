import collections


ResultTuple = collections.namedtuple('ResultTuple', ['value', 'type'])


class Error(Exception):
  """Base error class for this module."""


class TimeoutError(Error):
  """Timeout talking to the device."""


class NoModelOid(Error):
  """Could not locate a model for the switch."""


class SnmpError(Error):
  """A SNMP error occurred."""
