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
class MesonBuild:
  """Run meson setup, compile, install commands

  Parameters
  ----------
  root : str
    Path to root project directory
  meson : :class:`pyproj_meson <partis.pyproj.pptoml.pyproj_meson>`
  logger : logging.Logger
  """
  #-----------------------------------------------------------------------------
  def __init__(self, root, meson, logger):
    self.root = root
    self.meson = meson
    self.logger = logger
    self.meson_paths = dict(
      src_dir = None,
      build_dir = None,
      prefix = None )

  #-----------------------------------------------------------------------------
  def __enter__(self):

    if not self.meson.compile:
      return

    # check paths
    for k in ['src_dir', 'build_dir', 'prefix']:
      with validating(key = f"tool.pyproj.meson.{k}"):

        rel_path = self.meson[k]

        abs_path = osp.realpath( osp.join(
          self.root,
          rel_path ) )

        if osp.commonpath([self.root, abs_path]) != self.root:
          raise FileOutsideRootError(
            f"Must be within project root directory:"
            f"\n  file = \"{abs_path}\"\n  root = \"{self.root}\"")

        self.meson_paths[k] = abs_path

    src_dir = self.meson_paths['src_dir']
    build_dir = self.meson_paths['build_dir']
    prefix = self.meson_paths['prefix']

    with validating(key = f"tool.pyproj.meson.src_dir"):
      if not osp.exists(src_dir):
        raise ValidPathError(f"Source directory not found: {src_dir}")

    with validating(key = f"tool.pyproj.meson"):
      if osp.commonpath([build_dir, prefix]) == build_dir:
        raise ValidPathError(f"'prefix' cannot be inside 'build_dir': {build_dir}")

    for k in ['build_dir', 'prefix']:
      with validating(key = f"tool.pyproj.meson.{k}"):
        dir = self.meson_paths[k]

        if dir == self.root:
          raise ValidPathError(f"'{k}' cannot be root directory: {dir}")

        if not osp.exists(dir):
          os.makedirs(dir)

    self.logger.info(f"Running meson build")
    self.logger.info(f"Meson build dir: {build_dir}")
    self.logger.info(f"Meson prefix: {prefix}")

    # TODO: ensure any paths in setup_args are normalized

    setup_args = [
      'meson',
      'setup',
      *self.meson.setup_args,
      '--prefix',
      prefix,
      *[ meson_option_arg(k,v) for k,v in self.meson.options.items() ],
      build_dir,
      self.meson_paths['src_dir'] ]

    compile_args = [
      'meson',
      'compile',
      *self.meson.compile_args,
      '-C',
      build_dir ]

    install_args = [
      'meson',
      'install',
      *self.meson.install_args,
      '--no-rebuild',
      '-C',
      build_dir ]


    self.logger.debug(' '.join(setup_args))

    subprocess.check_call(setup_args)

    self.logger.debug(' '.join(compile_args))

    subprocess.check_call(compile_args)

    self.logger.debug(' '.join(install_args))

    subprocess.check_call(install_args)


  #-----------------------------------------------------------------------------
  def __exit__(self, type, value, traceback):

    if self.meson_paths['build_dir'] is not None and self.meson.build_clean:
      self.logger.info(f"Removing Meson build dir")
      shutil.rmtree(self.meson_paths['build_dir'])

    # do not handle any exceptions here
    return False
