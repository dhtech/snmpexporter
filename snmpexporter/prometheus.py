import collections
import logging


Metric = collections.namedtuple(
  'Metrics', ('name', 'type', 'labels', 'value'))


class Exporter(object):

  NUMERIC_TYPES = set([
    'COUNTER', 'COUNTER64', 'INTEGER', 'INTEGER32', 'TICKS',
    'GAUGE', 'ANNOTATED', 'UNSIGNED32'])

  def export(self, target, results):
    grouped_metrics = collections.defaultdict(dict)
    for result in results.values():
      grouped_metrics[(result.mib, result.obj)][result.index] = (
          self._export(target, result))
    for (mib, obj), metrics in grouped_metrics.items():
      for x in self.format_metrics(mib, obj, metrics):
        yield x

    # Export statistics
    yield '# HELP snmp_export_latency Latency breakdown for SNMP poll'
    yield '# TYPE snmp_export_latency gauge'
    for (step, latency) in target.timeline():
      yield 'snmp_export_latency{step="%s"} %s' % (step, latency)
    yield '# HELP snmp_export_errors Errors for SNMP poll'
    yield '# TYPE snmp_export_errors gauge'
    yield 'snmp_export_errors %s' % target.errors
    yield '# HELP snmp_export_timeouts Timeouts for SNMP poll'
    yield '# TYPE snmp_export_timeouts gauge'
    yield 'snmp_export_timeouts %s' % target.timeouts

  def _export(self, target, result):
    if result.data.type == 'COUNTER64' or result.data.type == 'COUNTER':
      metric_type = 'counter'
    elif result.data.type in self.NUMERIC_TYPES:
      metric_type = 'gauge'
    else:
      metric_type = 'blob'

    labels = dict(result.labels)
    labels['index'] = result.index

    return Metric(result.obj, metric_type, labels, result.data.value)

  def is_only_numeric(self, labels_map):
    for metric in labels_map.values():
      try:
        float(metric.value)
      except ValueError:
        return False
    return True

  def format_metrics(self, mib, obj, metrics):
    if not metrics:
      return
    out = []
    # Some vendors (e.g. Fortigate) choose to have decimal values as
    # OCTETSTR instead of a scaled value. Try to convert all values, if
    # we succeed export this metric as guage.
    convert_to_float = False
    metrics_type = metrics[list(metrics.keys())[0]].type
    if metrics_type == 'blob' and self.is_only_numeric(metrics):
      metrics_type = 'gauge'
      convert_to_float = True
    if metrics_type != 'counter' and metrics_type != 'gauge':
      return []
    out.append('# HELP {0} {1}::{0}'.format(obj, mib))
    out.append('# TYPE {0} {1}'.format(obj, metrics_type))
    for i in sorted(metrics.keys()):
      metric = metrics[i]
      if metric.type != metrics_type:
        # This happens if we have a collision somewhere ('local' is common)
        # Just ignore this for now.
        continue

      label_list = ['{0}="{1}"'.format(k, v) for k, v in metric.labels.items()]
      label_string = ','.join(label_list)
      instance = ''.join([obj, '{', label_string, '}'])

      if convert_to_float:
        value = float(metric.value)

      out.append('{0} {1}'.format(instance, metric.value))
    return out
