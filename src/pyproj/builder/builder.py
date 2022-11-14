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
  targets : :class:`pyproj_build <partis.pyproj.pptoml.pyproj_targets>`
  logger : logging.Logger
  """
  #-----------------------------------------------------------------------------
  def __init__(self,
    pyproj,
    root,
    targets,
    logger):

    self.pyproj = pyproj
    self.root = Path(root).resolve()
    self.targets = targets
    self.logger = logger
    self.target_paths = [
      dict(
        src_dir = target.src_dir,
        build_dir = target.build_dir,
        prefix = target.prefix )
      for target in targets ]

  #-----------------------------------------------------------------------------
  def __enter__(self):

    try:
      for i, (target, paths) in enumerate(zip(self.targets, self.target_paths)):
        if not target.enabled:
          self.logger.info(f"Skipping targets[{i}], disabled for environment markers")
          continue

        # check paths
        for k in ['src_dir', 'build_dir', 'prefix']:
          with validating(key = f"tool.pyproj.targets[{i}].{k}"):

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

        with validating(key = f"tool.pyproj.targets[{i}].src_dir"):
          if not src_dir.exists():
            raise ValidPathError(f"Source directory not found: {src_dir}")

        with validating(key = f"tool.pyproj.targets[{i}]"):
          if subdir(build_dir, prefix, check = False):
            raise ValidPathError(f"'prefix' cannot be inside 'build_dir': {build_dir}")

        for k in ['build_dir', 'prefix']:
          with validating(key = f"tool.pyproj.targets[{i}].{k}"):
            dir = paths[k]

            if dir == self.root:
              raise ValidPathError(f"'{k}' cannot be root directory: {dir}")

            dir.mkdir( parents = True, exist_ok = True )

        entry_point = EntryPoint(
          pyproj = self,
          root = self.root,
          name = f"tool.pyproj.targets[{i}]",
          logger = self.logger,
          entry = target.entry )

        self.logger.info(f"Running build[{i}]")
        self.logger.info(f"Source dir: {src_dir}")
        self.logger.info(f"Build dir: {build_dir}")
        self.logger.info(f"Prefix: {prefix}")

        entry_point(
          options = target.options,
          src_dir = src_dir,
          build_dir = build_dir,
          prefix = prefix,
          setup_args = target.setup_args,
          compile_args = target.compile_args,
          install_args = target.install_args,
          build_clean = target.build_clean )

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
    for i, (target, paths) in enumerate(zip(self.targets, self.target_paths)):
      build_dir = paths['build_dir']

      if build_dir is not None and build_dir.exists() and target.build_clean:
        self.logger.info(f"Removing build dir: {build_dir}")
        shutil.rmtree(build_dir)
