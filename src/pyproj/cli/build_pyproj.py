from __future__ import annotations
import sys
import os
from pathlib import Path
from subprocess import check_call
from partis.pyproj import (
  norm_dist_filename)
from partis.pyproj.backend import backend_init
from partis.pyproj.cache import cache_dir

#===============================================================================
def _prep_parser(subparsers):

  parser = subparsers.add_parser(
    'prep',
    help='runs binary distribution preparation steps')

  parser.add_argument(
    'path',
    type=Path,
    help='Path to project directory')

  parser.set_defaults(func = _prep_impl)

  return parser

#===============================================================================
def _prep_impl(args):
  _prep_pyproj(path = args.path)

#===============================================================================
def _prep_pyproj(
    path: Path,
    config_settings: dict|None = None):

  pyproj = backend_init(
    root = path,
    config_settings = config_settings,
    editable = True)

  pyproj.dist_prep()
  pyproj.dist_binary_prep()

#===============================================================================
def _rebuild_parser(subparsers):

  parser = subparsers.add_parser(
    'rebuild',
    help='re-runs binary distribution preparation')

  parser.add_argument(
    'path',
    type=Path,
    help='Path to project directory')

  parser.set_defaults(func = _rebuild_impl)

  return parser

#===============================================================================
def _rebuild_impl(args):
  _rebuild_pyproj(path = args.path)

#===============================================================================
def _rebuild_pyproj(
    path: Path,
    config_settings: dict|None = None):

  pyproj = backend_init(
    root = path,
    config_settings = config_settings,
    editable = True)

  if not any(target.enabled for target in pyproj.targets):
    print("Project has no build targets.")
    exit(0)

  pkg_name = norm_dist_filename(pyproj.pkg_info.name_normed)
  pyversion = '.'.join(str(n) for n in sys.version_info[:3])
  editable_root = cache_dir()/'editable'/f'{pkg_name}_{pyproj.pkg_info.version}_py{pyversion}'

  if not editable_root.exists():
    print(f"Editable install not found: {editable_root}")
    exit(1)

  print(f"Editable install: {editable_root}")

  venv_dir = editable_root/'build_venv'
  for bin in ['bin', 'Scripts']:
    if (venv_bin := venv_dir/bin).is_dir():
      break
  else:
    raise FileNotFoundError(f"No virtual environment bin directory: {venv_dir}")

  venv_py = venv_bin/Path(sys.executable).name

  if not (venv_py := venv_bin/Path(sys.executable).name).exists():
    print(f"No virtual environment interpreter: {venv_py}")
    exit(1)

  venv_env = {
    **os.environ,
    'VIRTUAL_ENV': str(venv_dir),
    'PATH': os.pathsep.join([str(venv_bin)] + os.environ['PATH'].split(os.pathsep))}

  check_call([
    venv_py, '-I', '-m', 'partis.pyproj.cli', 'prep',
    str(pyproj.root)],
    env = venv_env)
