from __future__ import annotations
from pathlib import Path
import argparse
from .init_pyproj import _init_pyproj

#===============================================================================
def main():
  parser = argparse.ArgumentParser(prog='partis-pyproj')

  parser.set_defaults(func = None)

  subparsers = parser.add_subparsers()

  init_parser = subparsers.add_parser(
    'init',
    help='Initialize template pyproject.toml')

  init_parser.add_argument(
    '--name',
    type=str,
    default=None,
    help='Project name')

  init_parser.add_argument(
    '--version',
    type=str,
    default='0.0.1',
    help='Initial project version')

  init_parser.add_argument(
    '--desc',
    type=str,
    default='',
    help='Project short description')

  init_parser.add_argument(
    'path',
    type=Path,
    help='Path of directory to create pyproject.toml')

  init_parser.set_defaults(func = _init_impl)

  args = parser.parse_args()

  if args.func is None:
    init_parser.print_help()
    return

  args.func(args)

#===============================================================================
def _init_impl(args):
  _init_pyproj(
    path = args.path,
    project = args.name,
    version = args.version,
    description = args.desc)

#===============================================================================
if __name__ == '__main__':
  main()
