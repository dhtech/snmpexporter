import os

from setuptools import setup, Extension

# the one version of this program: the file VERSION at the top
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, '..', 'VERSION')) as f:
  version = f.read().strip()

setup(name='mibresolver', version=version, ext_modules=[
  Extension('mibresolver', sources=['mibresolver.c'], libraries=['netsnmp'])])
