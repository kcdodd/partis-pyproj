from __future__ import annotations
from pathlib import Path
import logging
from .builder import (
  ProcessRunner)
from ..validate import (
  ValidPathError)

#===============================================================================
def process(
  pyproj,
  logger: logging.Logger,
  options: dict,
  work_dir: Path,
  src_dir: Path,
  build_dir: Path,
  prefix: Path,
  setup_args: list[str],
  compile_args: list[str],
  install_args: list[str],
  build_clean: bool,
  runner: ProcessRunner):
  """Run general three-part set of commands
  """

  if not ( build_dir.exists() and any(build_dir.iterdir()) ):
    # build directory is clean
    ...

  elif not build_clean:
    # skip setup if the build directory should be 'clean'
    setup_args = list()

  else:
    raise ValidPathError(
      f"'build_dir' is not empty, remove manually if this is intended or set 'build_clean = false': {build_dir}")


  for cmd in [setup_args, compile_args, install_args]:
    if cmd:
      runner.run(cmd)

