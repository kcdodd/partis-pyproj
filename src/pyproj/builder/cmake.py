import os
import os.path as osp
import tempfile
import shutil
import subprocess

from ..validate import (
  validating,
  ValidationError,
  ValidPathError,
  FileOutsideRootError )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def cmake_option_arg(k, v):
  """Convert python key-value pair to cmake ``-Dkey=value`` option
  """
  if isinstance(v, bool):
    v = ({True: 'ON', False: 'OFF'})[v]

  return f'-D{k}={v}'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def cmake(
  pyproj,
  logger,
  options,
  src_dir,
  build_dir,
  prefix,
  setup_args,
  compile_args,
  install_args,
  build_clean ):
  """Run cmake configure and install commands

  Parameters
  ----------
  pyproj : :class:`PyProjBase <partis.pyproj.pyproj.PyProjBase>`
  logger : logging.Logger
  options : dict
  src_dir : pathlib.Path
  build_dir : pathlib.Path
  prefix : pathlib.Path
  setup_args : list[str]
  compile_args : list[str]
  install_args : list[str]
  build_clean : bool
  """

  if not shutil.which('cmake'):
    raise ValueError(f"The 'cmake' program not found.")

  if not shutil.which('ninja'):
    raise ValueError(f"The 'ninja' program not found.")

  # TODO: ensure any paths in setup_args are normalized
  if not ( build_dir.exists() and any(build_dir.iterdir()) ):
    # only run setup if the build directory does not already exist (or is empty)
    setup_args = [
      'cmake',
      *setup_args,
      '-G',
      'Ninja',
      '--install-prefix',
      os.fspath(prefix),
      *[ cmake_option_arg(k,v) for k,v in options.items() ],
      '-B',
      os.fspath(build_dir),
      '-S',
      os.fspath(src_dir) ]

  elif not build_clean:
    # skip setup if the build directory should be 'clean'
    setup_args = list()

  else:
    raise ValidPathError(
      f"'build_dir' is not empty, remove manually if this is intended or set 'build_clean = false': {build_dir}")

  compile_args = [
    'cmake',
    *compile_args,
    '--build',
    os.fspath(build_dir) ]

  install_args = [
    'cmake',
    *install_args,
    '--install',
    os.fspath(build_dir) ]


  if setup_args:
    logger.debug(' '.join(setup_args))
    subprocess.check_call(setup_args)

  logger.debug(' '.join(compile_args))

  subprocess.check_call(compile_args)

  logger.debug(' '.join(install_args))

  subprocess.check_call(install_args)
