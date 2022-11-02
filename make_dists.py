# -*- coding: utf-8 -*-
"""CLI for building distribution of source, binary, and documentation

"""

import os
import os.path as osp 
from pathlib import Path
from pathlib import PurePath
from pathlib import PurePosixPath
import sys
import argparse
from argparse import RawTextHelpFormatter
import subprocess

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def main():
  parser = argparse.ArgumentParser(
    description = __doc__,
    formatter_class = RawTextHelpFormatter )

  parser.add_argument( "-o", "--outdir",
    type = str,
    default = None,
    help = "Output directory" )

  parser.add_argument( "--no-doc",
    action = 'store_true',
    help = "Do not generate documentation" )

  parser.add_argument( "--dist",
    nargs = '*',
    default = None,
    help = "dist type to make: 'wheel','sdist'" )

  args = parser.parse_args()


  out_dir = args.outdir

  root_dir = PurePosixPath( Path(__file__).absolute() ).parent

  if not out_dir:
    out_dir = Path(root_dir).joinpath('dist')
  if not Path('.').exists():
    Path(out_dir).mkdir(parents=True,exist_ok = True)

  subprocess.check_call([
    'python3',
    '-m',
    'pip',
    'install',
    'build' ])

  if os.environ.get('PIP_FIND_LINKS', '') == '':
    os.environ['PIP_FIND_LINKS'] = out_dir
  else:
    os.environ['PIP_FIND_LINKS'] = out_dir + ' ' + os.environ['PIP_FIND_LINKS']


  if args.dist is None:
    dists = list()
  else:
    dists = [ f'--{d}' for d in args.dist ]


  subprocess.check_call([
    'python3',
    '-m',
    'build',
    *dists,
    '-o',
    out_dir,
    root_dir ])

  if not args.no_doc:
    subprocess.check_call([
      'python3',
      '-m',
      'pip',
      'uninstall',
      '-y',
      'partis-pyproj' ])

    # remove from the pip cache to prevent using a previously installed distro.
    try:
      subprocess.check_call([
        'python3',
        '-m',
        'pip',
        'cache',
        'remove',
        "'partis-pyproj'" ])
    except:
      pass

    subprocess.check_call([
      'python3',
      '-m',
      'pip',
      'install',
      'partis-pyproj[doc]' ])

    subprocess.check_call([
      'python3',
      '-m',
      'doc',
      '-o',
      out_dir ])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
if __name__ == "__main__":
  main()
