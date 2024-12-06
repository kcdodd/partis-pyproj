import os
import os.path as osp
import tempfile
import shutil
import subprocess
from string import Template

from ..validate import (
  validating,
  ValidationError,
  ValidPathError,
  FileOutsideRootError )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def process(
  pyproj,
  logger,
  options,
  work_dir,
  src_dir,
  build_dir,
  prefix,
  setup_args,
  compile_args,
  install_args,
  build_clean,
  runner):
  """Run general three-part set of commands

  Parameters
  ----------
  pyproj : :class:`PyProjBase <partis.pyproj.pyproj.PyProjBase>`
  logger : logging.Logger
  options : dict
  work_dir: pathlib.Path
  src_dir : pathlib.Path
  build_dir : pathlib.Path
  prefix : pathlib.Path
  setup_args : list[str]
  compile_args : list[str]
  install_args : list[str]
  build_clean : bool
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

