

class Error(Exception):
  """Generic error class for this module"""


class LayerNotFound(Error):
  """The target has a layer that has no configuration"""


class SnmpTarget(object):
  def __init__(self, host, layer, config):
    if config.get('snmp', layer) is None:
      raise LayerNotFound(layer)
    self._read_config(**config[layer])
    self.host = host
    self.layer = layer
    self.full_host = "%s:%s" % (self.host, self.port)
    self.max_size = 256

  def _read_config(self, version, community=None,
      user=None, auth_proto=None, auth=None, priv_proto=None, priv=None,
      sec_level=None, port=161):
    self.version = version
    self.community = community
    self.user = user
    self.auth_proto = auth_proto
    self.auth = auth
    self.priv_proto = priv_proto
    self.priv = priv
    self.sec_level = sec_level
    self.port = port
