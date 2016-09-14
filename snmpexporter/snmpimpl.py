import logging
import sys


class SnmpImpl(object):

  def model(self):
    pass

  def vlans(self):
    pass

  def get(self, oid):
    pass

  def walk(self, oid, vlan=None):
    pass


class NetsnmpImpl(SnmpImpl):

  def __init__(self):
    import netsnmp
    self.netsnmp = netsnmp
    self.first_load = True

  def _snmp_session(self, target, vlan=None, timeout=1000000, retries=3):
    if self.first_load:
      # Loading MIBs can be very noisy, so we close stderr
      # Ideally we would just call netsnmp_register_loghandler but that isn't
      # exported :-(
      stderr = os.dup(sys.stderr.fileno())
      null = os.open(os.devnull, os.O_RDWR)
      os.close(sys.stderr.fileno())
      os.dup2(null, sys.stderr.fileno())
      os.close(null)

    if target.version == 3:
      context = ('vlan-%s' % vlan) if vlan else ''
      session = self.netsnmp.Session(Version=3, DestHost=target.full_host,
        SecName=target.user, SecLevel=target.sec_level, Context=context,
        AuthProto=target.auth_proto, AuthPass=target.auth,
        PrivProto=target.priv_proto, PrivPass=target.priv,
        UseNumeric=1, Timeout=timeout, Retries=retries)
    else:
      community = (
        '%s@%s' % (target.community, vlan)) if vlan else target.community
      session = self.netsnmp.Session(
        Version=target.version, DestHost=target.full_host,
        Community=community, UseNumeric=1, Timeout=timeout,
        Retries=retries)

    if first_load:
      # Restore stderr
      os.dup2(stderr, sys.stderr.fileno())
      os.close(stderr)
      self.first_load = False
    return session

  def walk(self, target, oid, vlan=None):
    sess = self._snmp_session(target, vlan)
    ret = {}
    nextoid = oid
    offset = 0

    # Abort the walk when it exits the OID tree we are interested in
    while nextoid.startswith(oid):
      var_list = self.netsnmp.VarList(self.netsnmp.Varbind(nextoid, offset))
      sess.getbulk(nonrepeaters=0, maxrepetitions=target.max_size,
                   varlist=var_list)

      # WORKAROUND FOR NEXUS BUG (2014-11-24)
      # Indy told blueCmd that Nexus silently drops the SNMP response
      # if the packet is fragmented. Try with large size first, but drop down
      # to smaller one.
      if sess.ErrorStr == 'Timeout':
        if target.max_size == 1:
          raise TimeoutError(
              'Timeout getting %s from %s' % (nextoid, self.host))
        target.max_size = int(target.max_size / 16)
        continue
      if sess.ErrorStr != '':
        raise SnmpError('SNMP error while walking host %s: %s' % (
          self.host, sess.ErrorStr))

      for result in var_list:
        currentoid = '%s.%s' % (result.tag, int(result.iid))
        # We don't want to save extra oids that the bulk walk might have
        # contained.
        if not currentoid.startswith(oid):
          break
        ret[currentoid] = ResultTuple(result.val, result.type)
      # Continue bulk walk
      offset = int(var_list[-1].iid)
      nextoid = var_list[-1].tag
    return ret

  def get(self, target, oid):
    sess = self._snmp_session(target, timeout=500000, retries=2)
    var = self.netsnmp.Varbind(oid)
    var_list = self.netsnmp.VarList(var)
    sess.get(var_list)
    if sess.ErrorStr != '':
      if sess.ErrorStr == 'Timeout':
        raise TimeoutError('Timeout getting %s from %s' % (oid, self.host))
      raise SnmpError('SNMP error while talking to host %s: %s' % (
        self.host, sess.ErrorStr))

    return {var.tag: ResultTuple(var.val, var.type)}

  def model(self, target):
    model_oids = [
        '.1.3.6.1.2.1.47.1.1.1.1.13.1',     # Normal switches
        '.1.3.6.1.2.1.47.1.1.1.1.13.1001',  # Stacked switches
        '.1.3.6.1.2.1.47.1.1.1.1.13.10',    # Nexus
        '.1.3.6.1.2.1.1.1.0',               # Other appliances (sysDescr)
    ]
    for oid in model_oids:
      model = self.get(target, oid)
      if not model:
        continue
      value = list(model.values()).pop().value
      if value:
        return value
    raise NoModelOid('No model OID contained a model')

  def vlans(self, target):
    try:
      oids = list(self.walk(target, '.1.3.6.1.4.1.9.9.46.1.3.1.1.2').keys())
      vlans = {int(x.split('.')[-1]) for x in oids}
      return vlans
    except ValueError as e:
      logging.info('ValueError while parsing VLAN for %s: %s', self.host, e)
      return []
