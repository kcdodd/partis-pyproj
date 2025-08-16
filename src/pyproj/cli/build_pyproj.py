from __future__ import annotations
from pathlib import Path
from partis.pyproj.backend import (
  backend_init)

#===============================================================================
def _build_parser(subparsers):

  parser = subparsers.add_parser(
    'build',
    help='Runs binary distribution preparation')

  parser.add_argument('-i', '--incremental', action='store_true')

  parser.add_argument(
    'path',
    type=Path,
    help='Path to project directory')

  parser.set_defaults(func = _build_impl)

  return parser

#===============================================================================
def _build_impl(args):
  _build_pyproj(
    path = args.path,
    incremental = args.incremental)

#===============================================================================
def _build_pyproj(
    path: Path,
    incremental: bool = False,
    config_settings: dict|None = None):

  pyproj = backend_init(
    root = path,
    config_settings = config_settings,
    editable = True,
    init_logging = not incremental)

  pyproj.dist_prep()
  pyproj.dist_binary_prep(incremental=incremental)
