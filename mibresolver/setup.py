from distutils.core import setup, Extension

setup(name='mibresolver', version='0.1', ext_modules=[
  Extension('mibresolver', sources=['mibresolver.c'], libraries=['netsnmp'])])
