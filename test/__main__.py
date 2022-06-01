"""Convenience CLI for running the tests

$ python -m test
"""

import os
import os.path as osp
import subprocess
import argparse
from argparse import RawTextHelpFormatter

parser = argparse.ArgumentParser(
  description = __doc__,
  formatter_class = RawTextHelpFormatter )

parser.add_argument( "-s", "--session",
  type = str,
  default = None,
  help = "session to run with nox (--list to see available sessions)" )

parser.add_argument( "--list",
  action = 'store_true',
  help = "list available nox sessions" )

args = parser.parse_args( )

subprocess.check_call([
  'nox',
  '-f',
  osp.join( osp.dirname(__file__), 'noxfile.py' ),
  *( ['-s', args.session ] if args.session else [] ),
  *( ['--list', ] if args.list else [] ) ])
