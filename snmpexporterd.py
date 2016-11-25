#!/usr/bin/env python3
import argparse
from concurrent import futures
import functools
import logging
import sys
import threading
import yaml

import snmpexporter
import snmpexporter.prometheus

from twisted.internet import reactor, task, endpoints
from twisted.python import log
from twisted.web import server, resource


# As we're using multiprocessing it's probably not needed for this to be
# thread-local, but why not.
tls = threading.local()
tls.snmpimpl = None


def poll(config, host, layer):
  logging.debug('Initializing Net-SNMP implemention')
  if not tls.snmpimpl:
    tls.snmpimpl = snmpexporter.snmpimpl.NetsnmpImpl()

  collections = config['collection']
  overrides = config['override']
  snmp_creds = config['snmp']

  logging.debug('Constructing SNMP target')
  target = snmpexporter.target.SnmpTarget(host, layer, snmp_creds)

  logging.debug('Creating SNMP poller')
  poller = snmpexporter.poller.Poller(collections, overrides, tls.snmpimpl)

  logging.debug('Starting poll')
  data, timeouts, errors = poller.poll(target)
  return target, data, timeouts, errors


def annotate(config, resolver, f):
  target, data, timeouts, errors = f

  annotator_config = config['annotator']

  logging.debug('Creating result annotator')
  annotator = snmpexporter.annotator.Annotator(annotator_config, resolver)

  logging.debug('Starting annotation')
  result = annotator.annotate(data)

  exporter = snmpexporter.prometheus.Exporter()
  return exporter.export(target, result)


class PollerResource(resource.Resource):
  isLeaf = True

  def __init__(self, config_file, poller_pool, annotator_pool):
    super(PollerResource).__init__()
    # Use process pollers as netsnmp is not behaving well using just threads
    logging.debug('Starting poller pool ...')
    self.poller_executor = futures.ProcessPoolExecutor(
        max_workers=poller_pool)
    # Start MIB resolver after processes above (or it will fork it as well)
    logging.debug('Initializing MIB resolver ...')
    import mibresolver
    self.resolver = mibresolver

    logging.debug('Starting annotation pool ...')
    # .. but annotators are just CPU, so use lightweight threads.
    self.annotator_executor = futures.ThreadPoolExecutor(
        max_workers=annotator_pool)

    with open(config_file, 'r') as f:
      self.config = yaml.safe_load(f.read())

  def _annotate_done(self, request, f):
    if f.exception():
      logging.error('Annotator failed: %s', repr(f.exception()))
      request.setResponseCode(500)
      request.write(('500 Annotator failed: %s' % repr(f.exception())).encode())
      request.finish()
      return

    for row in f.result():
      request.write(row.encode())
      request.write('\n'.encode())
    request.finish()

  def _annotate_done(self, f):
    logging.debug('Request cancelled, cancelling future %s', f)
    f.cancel()

  def _poll_done(self, request, f):
    if f.exception():
      logging.error('Poller failed: %s', repr(f.exception()))
      request.setResponseCode(500)
      request.write(('500 Poller failed: %s' % repr(f.exception())).encode())
      request.finish()
      return

    logging.debug('Poller done, starting annotation')
    f = self.annotator_executor.submit(
        annotate, self.config, self.resolver, f.result())
    f.add_done_callback(functools.partial(self._annotate_done, request))
    request.notifyFinish().addErrback(self._responseFailed, f)

  def render_GET(self, request):
    path = request.path.decode()
    if path == '/probe':
      return self.probe(request)
    elif path == '/healthy':
      return self.healthy(request)
    else:
      logging.info('Not found: %s', path)
      request.setResponseCode(404)
      return '404 Not Found'.encode()

  def healthy(self, request):
    return '200 I am healthy'.encode()

  def probe(self, request):
    layer = request.args.get('layer'.encode(), [None])[0]
    target = request.args.get('target'.encode(), [None])[0]

    if not layer or not target:
      request.setResponseCode(400)
      return '400 Missing layer or target parameter'.encode()

    layer = layer.decode()
    target = target.decode()

    f = self.poller_executor.submit(poll, self.config, target, layer)
    f.add_done_callback(functools.partial(self._poll_done, request))

    logging.debug('Starting poll')
    request.notifyFinish().addErrback(self._responseFailed, f)
    return server.NOT_DONE_YET


if __name__ == '__main__':
  import argparse

  parser = argparse.ArgumentParser(description='One-shot SNMP exporter.')
  parser.add_argument('--config', dest='config_file', type=str,
          help='config file to load', default='/etc/snmpexporter.yaml')
  parser.add_argument('--log-level', dest='log_level', type=str,
          help='log level', default='INFO')
  parser.add_argument('--poller-pool', dest='poller_pool', type=int,
          help='number of simultaneous polls to do', default=10)
  parser.add_argument('--annotator-pool', dest='annotator_pool', type=int,
          help='number of threads to use to annotate', default=5)
  parser.add_argument('--port', dest='port', type=int,
          help='port to listen to', default=9190)
  args = parser.parse_args()

  # Logging setup
  observer = log.PythonLoggingObserver()
  observer.start()

  root = logging.getLogger()
  ch = logging.StreamHandler(sys.stderr)
  formatter = logging.Formatter( '%(asctime)s - %(name)s - '
              '%(levelname)s - %(message)s' )
  ch.setFormatter(formatter)
  root.addHandler(ch)
  root.setLevel(logging.getLevelName(args.log_level))

  pr = PollerResource(
      args.config_file, args.poller_pool, args.annotator_pool)

  factory = server.Site(pr)

  logging.debug('Starting web server on port %d', args.port)
  endpoint = endpoints.TCP4ServerEndpoint(reactor, args.port)
  endpoint.listen(factory)
  reactor.run()
