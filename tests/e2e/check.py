#!/usr/bin/env python3
"""Ask a URL and check the answer (for .github/try.sh).

  check.py URL [--status N] [--has REGEX ...] [--lacks REGEX ...]
           [--wait SECONDS] [--refused]

--wait: keep trying that long while nothing listens yet. --refused:
the connection must be refused (nothing may listen there).
"""
import argparse
import re
import sys
import time
import urllib.error
import urllib.request


def ask(url):
  try:
    with urllib.request.urlopen(url, timeout=120) as f:
      return f.status, f.read().decode()
  except urllib.error.HTTPError as e:
    return e.code, e.read().decode()


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument('url')
  ap.add_argument('--status', type=int, default=200)
  ap.add_argument('--has', action='append', default=[])
  ap.add_argument('--lacks', action='append', default=[])
  ap.add_argument('--wait', type=float, default=0)
  ap.add_argument('--refused', action='store_true')
  args = ap.parse_args()

  deadline = time.time() + args.wait
  while True:
    try:
      status, body = ask(args.url)
      break
    except (urllib.error.URLError, ConnectionError) as e:
      if args.refused:
        print('ok: %s refuses (%s)' % (args.url, e))
        return
      if time.time() >= deadline:
        sys.exit('%s: no answer: %s' % (args.url, e))
      time.sleep(0.5)
  if args.refused:
    sys.exit('%s answers (%d) - nothing may listen there' % (
        args.url, status))

  faults = []
  if status != args.status:
    faults.append('status %d, wanted %d' % (status, args.status))
  for regex in args.has:
    if not re.search(regex, body, re.M):
      faults.append('nothing matches %r' % regex)
  for regex in args.lacks:
    m = re.search(regex, body, re.M)
    if m:
      faults.append('%r matches: %s' % (regex, m.group(0)))
  lines = body.splitlines()
  if faults:
    print('\n'.join(lines[:60]))
    sys.exit('%s: %s' % (args.url, '; '.join(faults)))
  print('ok: %s: %d, %d lines' % (args.url, status, len(lines)))
  for regex in args.has:
    print('    ' + re.search(regex, body, re.M).group(0))


if __name__ == '__main__':
  main()
