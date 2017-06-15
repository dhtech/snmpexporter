#!/usr/bin/env python3
import argparse
from concurrent import futures
import functools
import logging
import objgraph
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


# Used to test health of the executors
def do_nothing():
  pass


def poll(config, host, layer):
  try:
    if not tls.snmpimpl:
      logging.debug('Initializing Net-SNMP implemention')
      tls.snmpimpl = snmpexporter.snmpimpl.NetsnmpImpl()

    collections = config['collection']
    overrides = config['override']
    snmp_creds = config['snmp']

    logging.debug('Constructing SNMP target')
    target = snmpexporter.target.SnmpTarget(host, layer, snmp_creds)

    target.start('poll')

    logging.debug('Creating SNMP poller')
    poller = snmpexporter.poller.Poller(collections, overrides, tls.snmpimpl)

    logging.debug('Starting poll')
    data, timeouts, errors = poller.poll(target)
    target.add_timeouts(timeouts)
    target.add_errors(errors)

    return target, data
  except:
    logging.exception('Poll exception')
    raise


def annotate(config, resolver, f):
  try:
    target, data = f

    annotator_config = config['annotator']

    target.start('annotate')

    logging.debug('Creating result annotator')
    annotator = snmpexporter.annotator.Annotator(annotator_config, resolver)

    logging.debug('Starting annotation')
    result = annotator.annotate(data)

    target.done()

    exporter = snmpexporter.prometheus.Exporter()
    return exporter.export(target, result)
  except:
    logging.exception('Annotate exception')
    raise


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
    self.config_file = config_file

  def _response_failed(self, err, f):
    logging.debug('Request cancelled, cancelling future %s', f)
    f.cancel()

  def _reactor_annotate_done(self, request, f):
    reactor.callFromThread(self._annotate_done, request, f)

  def _annotate_done(self, request, f):
    if f.exception():
      logging.error('Annotator failed: %s', repr(f.exception()))
      request.setResponseCode(500, message=(
          'Annotator failed: %s' % repr(f.exception())).encode())
      request.finish()
      return

    for row in f.result():
      request.write(row.encode())
      request.write('\n'.encode())
    request.finish()

  def _reactor_poll_done(self, config, request, f):
    reactor.callFromThread(self._poll_done, config, request, f)

  def _poll_done(self, config, request, f):
    if f.exception():
      logging.error('Poller failed: %s', repr(f.exception()))
      request.setResponseCode(500, message=(
          'Poller failed: %s' % repr(f.exception())).encode())
      request.finish()
      return

    logging.debug('Poller done, starting annotation')
    f = self.annotator_executor.submit(
        annotate, config, self.resolver, f.result())
    f.add_done_callback(functools.partial(self._reactor_annotate_done, request))
    request.notifyFinish().addErrback(self._response_failed, f)

  def render_GET(self, request):
    path = request.path.decode()
    if path == '/probe':
      return self.probe(request)
    elif path == '/healthy':
      return self.healthy(request)
    elif path == '/objects':
      return self.objects(request)
    else:
      logging.info('Not found: %s', path)
      request.setResponseCode(404)
      return '404 Not Found'.encode()

  def objects(self, request):
    types = objgraph.most_common_types(limit=1000)
    request.write('# HELP objgraph_objects active objects in memory'.encode())
    request.write('# TYPE objgraph_objects gauge'.encode())
    for name, count in types:
      request.write(
              ('objgraph_objects{name="%s"} %s\n' % (name, count)).encode())
    return bytes()

  def _annotator_executor_healthy(self, request, completed_f):
    if completed_f.exception() or completed_f.cancelled():
      request.setResponseCode(500, message=(
          'Annotator health failed: %s' % repr(
              completed_f.exception())).encode())
      request.finish()
      return
    request.write('I am healthy'.encode())
    request.finish()

  def _poller_executor_healthy(self, request, completed_f):
    if completed_f.exception() or completed_f.cancelled():
      request.setResponseCode(500, message=(
          'Poller health failed: %s' % repr(completed_f.exception())).encode())
      request.finish()
      return
    f = self.annotator_executor.submit(do_nothing)
    f.add_done_callback(
            lambda f: reactor.callFromThread(
                self._annotator_executor_healthy, request, f))

  def healthy(self, request):
    # Send the healthy request through the pipeline executors to see
    # that everything works.
    f = self.poller_executor.submit(do_nothing)
    logging.debug('Starting healthy poll')
    f.add_done_callback(
            lambda f: reactor.callFromThread(
                self._poller_executor_healthy, request, f))
    request.notifyFinish().addErrback(self._response_failed, f)
    return server.NOT_DONE_YET

  def probe(self, request):
    layer = request.args.get('layer'.encode(), [None])[0]
    target = request.args.get('target'.encode(), [None])[0]

    if not layer or not target:
      request.setResponseCode(400)
      return '400 Missing layer or target parameter'.encode()

    layer = layer.decode()
    target = target.decode()

    with open(self.config_file, 'r') as f:
      config = yaml.safe_load(f.read())

    f = self.poller_executor.submit(poll, config, target, layer)
    f.add_done_callback(
        functools.partial(self._reactor_poll_done, config, request))

    logging.debug('Starting poll')
    request.notifyFinish().addErrback(self._response_failed, f)
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
