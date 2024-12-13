from __future__ import annotations
import os
import shutil

#===============================================================================
def meson_option_arg(k, v):
  """Convert python key-value pair to meson ``-Dkey=value`` option
  """
  if isinstance(v, bool):
    v = ({True: 'true', False: 'false'})[v]

  return f'-D{k}={v}'

#===============================================================================
def meson(
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
  """Run meson setup, compile, install commands

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

  if not shutil.which('meson'):
    raise ValueError("The 'meson' program not found.")

  if not shutil.which('ninja'):
    raise ValueError("The 'ninja' program not found.")

  os.environ['MESON_FORCE_BACKTRACE'] = '1'

  # TODO: ensure any paths in setup_args are normalized
  if not build_clean:
    # skip setup if the build directory already populated
    setup_args = list()
  else:
    # only run setup if the build directory does not already exist (or is empty)
    setup_args = [
      'meson',
      'setup',
      *setup_args,
      '--prefix',
      str(prefix),
      *[ meson_option_arg(k,v) for k,v in options.items() ],
      str(build_dir),
      str(src_dir) ]

  compile_args = [
    'meson',
    'compile',
    *compile_args,
    '-C',
    str(build_dir) ]

  install_args = [
    'meson',
    'install',
    *install_args,
    '--no-rebuild',
    '-C',
    str(build_dir) ]


  if setup_args:
    runner.run(setup_args)

  runner.run(compile_args)
  runner.run(install_args)
