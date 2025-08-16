from __future__ import annotations
from pathlib import Path
import argparse
from .init_pyproj import _init_parser
from .build_pyproj import _build_parser

#===============================================================================
def main():
  parser = argparse.ArgumentParser(prog='partis-pyproj')

  parser.set_defaults(func = None)

  subparsers = parser.add_subparsers()
  init_parser = _init_parser(subparsers)
  build_parser = _build_parser(subparsers)

  args = parser.parse_args()

  if args.func is None:
    init_parser.print_help()
    return

  args.func(args)

#===============================================================================
if __name__ == '__main__':
  main()
