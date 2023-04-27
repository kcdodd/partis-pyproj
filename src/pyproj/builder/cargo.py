from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess

from ..pyproj import PyProjBase
from logging import Logger

from ..validate import (
  validating,
  ValidationError,
  ValidPathError,
  FileOutsideRootError )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def cargo(
  pyproj: PyProjBase,
  logger: Logger,
  options: dict,
  src_dir: Path,
  build_dir: Path,
  prefix: Path,
  setup_args: list[str],
  compile_args: list[str],
  install_args: list[str],
  build_clean: bool ):
  """Run cargo build
  """

  if not shutil.which('cargo'):
    raise ValueError(f"The 'cargo' program not found.")

  if setup_args or install_args:
    raise ValueError(
      f"cargo builder supports 'compile_args', not 'setup_args' or 'install_args': {setup_args}, {install_args}")

  compile_args = [
    'cargo',
    'build',
    *compile_args,
    '--target-dir',
    str(build_dir) ]

  install_args = [
    'cargo',
    'install',
    *install_args,
    '--target-dir',
    str(build_dir),
    '--root', str(prefix) ]

  logger.debug(' '.join(compile_args))

  subprocess.check_call(compile_args)

