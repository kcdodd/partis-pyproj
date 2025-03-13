from __future__ import annotations
import shutil

#===============================================================================
def cmake_option_arg(k, v):
  """Convert python key-value pair to cmake ``-Dkey=value`` option
  """
  typename = ''

  if isinstance(v, bool):
    typename = ':BOOL'
    v = ({True: 'ON', False: 'OFF'})[v]

  return f'-D{k}{typename}={v}'

#===============================================================================
def cmake(
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
    raise ValueError("The 'cmake' program not found.")

  if not shutil.which('ninja'):
    raise ValueError("The 'ninja' program not found.")

  # TODO: ensure any paths in setup_args are normalized
  if not build_clean:
    # skip setup if the build directory
    setup_args = list()
  else:
    # only run setup if the build directory does not already exist (or is empty)
    setup_args = [
      'cmake',
      *setup_args,
      '-G',
      'Ninja',
      '--install-prefix',
      str(prefix),
      *[ cmake_option_arg(k,v) for k,v in options.items() ],
      '-B',
      str(build_dir),
      '-S',
      str(src_dir) ]

  compile_args = [
    'cmake',
    '--build',
    str(build_dir),
    *compile_args]

  install_args = [
    'cmake',
    *install_args,
    '--install',
    str(build_dir) ]


  if setup_args:
    runner.run(setup_args)

  runner.run(compile_args)
  runner.run(install_args)
