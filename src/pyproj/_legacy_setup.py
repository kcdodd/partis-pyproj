"""Usage of `setup.py` is deprecated, and is supplied only for legacy installation.
"""
import sys
import os
import os.path as osp
import importlib
import logging
import argparse
import subprocess
import tempfile
from argparse import RawTextHelpFormatter
logger = logging.getLogger(__name__)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def egg_info( args ):

  logger.warning(
    "running legacy 'setup.py egg_info'" )

  dir = osp.join( args.egg_base, EGG_INFO_NAME )

  if not osp.exists( dir ):
    os.mkdir( dir )

  with open( osp.join( dir, 'PKG-INFO' ), 'wb' ) as fp:
    fp.write( PKG_INFO )

  with open( osp.join( dir, 'setup_requires.txt' ), 'wb' ) as fp:
    fp.write( b'' )

  with open( osp.join( dir, 'requires.txt' ), 'wb' ) as fp:
    fp.write( REQUIRES )

  with open( osp.join( dir, 'SOURCES.txt' ), 'wb' ) as fp:
    fp.write( SOURCES )

  with open( osp.join( dir, 'top_level.txt' ), 'wb' ) as fp:
    fp.write( TOP_LEVEL )

  with open( osp.join( dir, 'entry_points.txt' ), 'wb' ) as fp:
    fp.write( ENTRY_POINTS )

  with open( osp.join( dir, 'dependency_links.txt' ), 'wb' ) as fp:
    fp.write( b'' )

  with open( osp.join( dir, 'not-zip-safe' ), 'wb' ) as fp:
    fp.write( b'' )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def bdist_wheel( args ):

  logger.warning(
    "running legacy 'setup.py bdist_wheel'" )

  sys.path = backend_path + sys.path

  backend = importlib.import_module( build_backend )

  backend.build_wheel(
    wheel_directory = args.dist_dir or args.bdist_dir or '.' )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def install( args ):

  logger.warning(
    "running legacy 'setup.py install'" )

  reqs = [ f"{{r}}" for r in build_requires ]

  subprocess.check_call([
    sys.executable,
    '-m',
    'pip',
    'install',
    *reqs ] )

  sys.path = backend_path + sys.path

  backend = importlib.import_module( build_backend )

  with tempfile.TemporaryDirectory() as tmpdir:
    wheel_name = backend.build_wheel(
      wheel_directory = tmpdir )

    subprocess.check_call([
      sys.executable,
      '-m',
      'pip',
      'install',
      osp.join(tmpdir, wheel_name) ])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dummy( args ):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def main():

  logging.basicConfig(
    level = logging.INFO,
    format = "{{name}}:{{levelname}}: {{message}}",
    style = "{{" )


  logger.warning(
    "'setup.py' is deprecated, limited support for legacy installs. Upgrade pip." )

  parser = argparse.ArgumentParser(
    description = __doc__,
    formatter_class = RawTextHelpFormatter )

  subparsers = parser.add_subparsers()

  #.............................................................................
  egg_info_parser = subparsers.add_parser( 'egg_info' )

  egg_info_parser.set_defaults( func = egg_info )

  egg_info_parser.add_argument( "-e", "--egg-base",
    type = str,
    default = '.' )

  #.............................................................................
  bdist_wheel_parser = subparsers.add_parser( 'bdist_wheel' )

  bdist_wheel_parser.set_defaults( func = bdist_wheel )

  bdist_wheel_parser.add_argument( "-b", "--bdist-dir",
    type = str,
    default = '' )

  bdist_wheel_parser.add_argument( "-d", "--dist-dir",
    type = str,
    default = '' )

  bdist_wheel_parser.add_argument( "--python-tag",
    type = str,
    default = None )

  bdist_wheel_parser.add_argument( "--plat-name",
    type = str,
    default = None )

  bdist_wheel_parser.add_argument( "--py-limited-api",
    type = str,
    default = None )

  bdist_wheel_parser.add_argument( "--build-number",
    type = str,
    default = None )

  #.............................................................................
  install_parser = subparsers.add_parser( 'install' )

  install_parser.set_defaults( func = install )

  install_parser.add_argument( "--record",
    type = str,
    default = None )

  install_parser.add_argument( "--install-headers",
    type = str,
    default = None )

  install_parser.add_argument( "--compile",
    action='store_true' )

  install_parser.add_argument( "--single-version-externally-managed",
    action='store_true' )

  #.............................................................................
  clean_parser = subparsers.add_parser( 'clean' )

  clean_parser.set_defaults( func = dummy )

  clean_parser.add_argument( "-a", "--all",
    action='store_true' )

  args = parser.parse_args( )

  args.func( args )


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# NOTE: these are templated literal values substituded by the backend when
# building the source distribution

build_backend = {build_backend}
backend_path = {backend_path}
build_requires = {build_requires}

EGG_INFO_NAME = {egg_info_name}

PKG_INFO = {pkg_info}

REQUIRES = {requires}

SOURCES = {sources}

TOP_LEVEL = {top_level}

ENTRY_POINTS = {entry_points}

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

if __name__ == "__main__":
  exit( main() )
