import os
import os.path as osp
import tempfile
import shutil
import subprocess
from pathlib import Path

from ..validate import (
  validating,
  ValidationError,
  ValidPathError,
  FileOutsideRootError )

from ..load_module import EntryPoint

from ..path import (
  subdir )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Builder:
  """Run build setup, compile, install commands

  Parameters
  ----------
  root : str | pathlib.Path
    Path to root project directory
  builds : :class:`pyproj_build <partis.pyproj.pptoml.pyproj_build>`
  logger : logging.Logger
  """
  #-----------------------------------------------------------------------------
  def __init__(self,
    pyproj,
    root,
    builds,
    logger):

    self.pyproj = pyproj
    self.root = Path(root).resolve()
    self.builds = builds
    self.logger = logger
    self.build_paths = [
      dict(
        src_dir = build.src_dir,
        build_dir = build.build_dir,
        prefix = build.prefix )
      for build in builds ]

  #-----------------------------------------------------------------------------
  def __enter__(self):

    try:
      for i, (build, paths) in enumerate(zip(self.builds, self.build_paths)):
        if not build.enabled:
          self.logger.info(f"Skipping build[{i}], disabled for environment markers")
          continue

        # check paths
        for k in ['src_dir', 'build_dir', 'prefix']:
          with validating(key = f"tool.pyproj.build[{i}].{k}"):

            rel_path = paths[k]

            abs_path = (self.root / rel_path).resolve()

            if not subdir(self.root, abs_path, check = False):
              raise FileOutsideRootError(
                f"Must be within project root directory:"
                f"\n  file = \"{abs_path}\"\n  root = \"{self.root}\"")


            paths[k] = abs_path

        src_dir = paths['src_dir']
        build_dir = paths['build_dir']
        prefix = paths['prefix']

        with validating(key = f"tool.pyproj.build[{i}].src_dir"):
          if not src_dir.exists():
            raise ValidPathError(f"Source directory not found: {src_dir}")

        with validating(key = f"tool.pyproj.build[{i}]"):
          if subdir(build_dir, prefix, check = False):
            raise ValidPathError(f"'prefix' cannot be inside 'build_dir': {build_dir}")

        for k in ['build_dir', 'prefix']:
          with validating(key = f"tool.pyproj.build[{i}].{k}"):
            dir = paths[k]

            if dir == self.root:
              raise ValidPathError(f"'{k}' cannot be root directory: {dir}")

            dir.mkdir( parents = True, exist_ok = True )

        entry_point = EntryPoint(
          pyproj = self,
          root = self.root,
          name = f"tool.pyproj.build[{i}]",
          logger = self.logger,
          entry = build.entry )

        self.logger.info(f"Running build[{i}]")
        self.logger.info(f"Source dir: {src_dir}")
        self.logger.info(f"Build dir: {build_dir}")
        self.logger.info(f"Prefix: {prefix}")

        entry_point(
          options = build.options,
          src_dir = src_dir,
          build_dir = build_dir,
          prefix = prefix,
          setup_args = build.setup_args,
          compile_args = build.compile_args,
          install_args = build.install_args,
          build_clean = build.build_clean )

    except:
      self.build_clean()
      raise

  #-----------------------------------------------------------------------------
  def __exit__(self, type, value, traceback):
    self.build_clean()

    # do not handle any exceptions here
    return False

  #-----------------------------------------------------------------------------
  def build_clean(self):
    for i, (build, paths) in enumerate(zip(self.builds, self.build_paths)):
      build_dir = paths['build_dir']

      if build_dir is not None and build_dir.exists() and build.build_clean:
        self.logger.info(f"Removing build dir: {build_dir}")
        shutil.rmtree(build_dir)
