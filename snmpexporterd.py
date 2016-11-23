#!/usr/bin/env python3
import argparse
import os
import subprocess

from flask import Flask


def main(config_file, port):
  app = Flask(__name__)
  @app.route('/poll/<layer>/<device>')
  def poll(layer, device):
    cmd = os.path.join(os.path.dirname(__file__), 'snmpexport.py')
    return subprocess.check_output(
        [cmd, '--config', config_file, '--annotate', device, layer])

  app.run(debug=True, threaded=True, port=port)


if __name__ == '__main__':
  import argparse

  parser = argparse.ArgumentParser(description='One-shot SNMP exporter.')
  parser.add_argument('--config', dest='config_file', type=str,
          help='config file to load', default='/etc/snmpexporter.yaml')
  parser.add_argument('--port', dest='port', type=int,
          help='port to listen to', default=9190)
  args = parser.parse_args()

  main(args.config_file, args.port)
