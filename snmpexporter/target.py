import time


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
    self.timeouts = 0
    self.errors = 0
    self.markers = []

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

  def add_timeouts(self, timeouts):
    self.timeouts = self.timeouts + timeouts

  def add_errors(self, errors):
    self.errors = self.errors + errors

  def start(self, step):
    self.markers.append((step, time.time()))

  def done(self):
    self.markers.append(('done', time.time()))

  def timeline(self):
    return [
        (fro[0], to[1] - fro[1])
        for fro, to in zip(self.markers, self.markers[1:])]
