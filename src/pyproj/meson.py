import os
import os.path as osp
import tempfile
import shutil
import subprocess

from .validate import (
  validating,
  ValidationError,
  ValidPathError,
  FileOutsideRootError )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def meson_option_arg(k, v):
  """Convert python key-value pair to meson ``-Dkey=value`` option
  """
  if isinstance(v, bool):
    v = ({True: 'true', False: 'false'})[v]

  return f'-D{k}={v}'

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def build(
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
  """Run meson setup, compile, install commands
  """

  if not shutil.which('meson'):
    raise ValueError(f"The 'meson' program not found.")

  if not shutil.which('ninja'):
    raise ValueError(f"The 'ninja' program not found.")

  # TODO: ensure any paths in setup_args are normalized
  if not ( osp.exists(build_dir) and os.listdir(build_dir) ):
    # only run setup if the build directory does not already exist
    setup_args = [
      'meson',
      'setup',
      *setup_args,
      '--prefix',
      prefix,
      *[ meson_option_arg(k,v) for k,v in options.items() ],
      build_dir,
      src_dir ]

  elif not build_clean:
    # only re-compile if the build directory should be 'clean'
    setup_args = list()

  else:
    raise ValidPathError(
      f"'build_dir' is not empty, remove manually if this is intended or set 'build_clean = false': {build_dir}")

  compile_args = [
    'meson',
    'compile',
    *compile_args,
    '-C',
    build_dir ]

  install_args = [
    'meson',
    'install',
    *install_args,
    '--no-rebuild',
    '-C',
    build_dir ]


  if setup_args:
    logger.debug(' '.join(setup_args))
    subprocess.check_call(setup_args)

  logger.debug(' '.join(compile_args))

  subprocess.check_call(compile_args)

  logger.debug(' '.join(install_args))

  subprocess.check_call(install_args)
