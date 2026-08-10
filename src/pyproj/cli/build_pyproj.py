from __future__ import annotations
import sys
import os
import shutil
from pathlib import Path
from subprocess import check_call
from partis.pyproj import (
  norm_dist_filename,
  dist_build,
  dist_binary_editable)
from partis.pyproj.backend import backend_init, _run_editable_py

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
    'root',
    type=Path,
    help='Path to project root directory')

  parser.set_defaults(func = _rebuild_impl)

  return parser

#===============================================================================
def _rebuild_impl(args):
  _rebuild_pyproj(root = args.root)

#===============================================================================
def _rebuild_pyproj(
    root: Path,
    config_settings: dict|None = None):

  pyproj = backend_init(
    root = root,
    config_settings = config_settings,
    editable = True)

  editable_root = pyproj.editable_root

  if not editable_root.exists():
    print(f"Editable installation not found: {editable_root}")
    exit(1)

  print(f"Rebuilding editable installation: {editable_root}")
  whl_root = editable_root/'wheel'
  # NOTE: out-of-tree, see 'PyProjBase.build_venv_dir'
  venv_dir = pyproj.build_venv_dir

  # NOTE: the build environment is in the user cache, so it can be removed
  # independently of the in-tree editable installation
  if not venv_dir.exists():
    print(
      f"Build environment not found: {venv_dir}\n"
      f"Re-install the editable distribution to re-create it.")
    exit(1)

  _run_editable_py(
    venv_dir,
    ['-I', '-m', 'partis.pyproj.cli', 'prep', str(pyproj.root)])

  if whl_root.exists():
    shutil.rmtree(whl_root)

  cwd = os.getcwd()
  try:
    os.chdir(root)
    with dist_binary_editable(
      root = root,
      pptoml_checksum = pyproj.pptoml_checksum,
      whl_root = whl_root,
      pkg_info = pyproj.pkg_info,
      build = dist_build(
        pyproj.binary.get('build_number', None),
        pyproj.binary.get('build_suffix', None) ),
      compat = pyproj.binary.compat_tags,
      outdir = editable_root,
      logger = pyproj.logger ) as dist:

      pyproj.dist_binary_copy(
        dist = dist )

      record_hash = dist.finalize()

  finally:
    os.chdir(cwd)


  pyproj.logger.debug(
    f"Top level packages {dist.top_level}")
