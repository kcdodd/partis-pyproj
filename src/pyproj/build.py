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
class Build:
  """Run meson setup, compile, install commands

  Parameters
  ----------
  root : str
    Path to root project directory
  builds : :class:`pyproj_build <partis.pyproj.pptoml.pyproj_builds>`
  logger : logging.Logger
  """
  #-----------------------------------------------------------------------------
  def __init__(self,
    pyproj,
    root,
    builds,
    logger):

    self.pyproj = pyproj
    self.root = root
    self.builds = builds
    self.logger = logger
    self.build_paths = len(builds)*[dict(
      src_dir = None,
      build_dir = None,
      prefix = None )]

  #-----------------------------------------------------------------------------
  def __enter__(self):

    try:
      for i, (build, paths) in enumerate(zip(self.builds, self.build_paths)):
        if not build.marker.evaluate():
          self.logger.info(f"Skipping build[{i}] for environment: {build.marker}")
          continue

        # check paths
        for k in ['src_dir', 'build_dir', 'prefix']:
          with validating(key = f"tool.pyproj.build[{i}].{k}"):

            rel_path = paths[k]

            abs_path = osp.realpath( osp.join(
              self.root,
              rel_path ) )

            if osp.commonpath([self.root, abs_path]) != self.root:
              raise FileOutsideRootError(
                f"Must be within project root directory:"
                f"\n  file = \"{abs_path}\"\n  root = \"{self.root}\"")

            paths[k] = abs_path

        src_dir = paths['src_dir']
        build_dir = paths['build_dir']
        prefix = paths['prefix']

        with validating(key = f"tool.pyproj.build[{i}].src_dir"):
          if not osp.exists(src_dir):
            raise ValidPathError(f"Source directory not found: {src_dir}")

        with validating(key = f"tool.pyproj.build[{i}]"):
          if osp.commonpath([build_dir, prefix]) == build_dir:
            raise ValidPathError(f"'prefix' cannot be inside 'build_dir': {build_dir}")

        for k in ['build_dir', 'prefix']:
          with validating(key = f"tool.pyproj.build[{i}].{k}"):
            dir = paths[k]

            if dir == self.root:
              raise ValidPathError(f"'{k}' cannot be root directory: {dir}")

            if not osp.exists(dir):
              os.makedirs(dir)

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
          setup_args = setup_args,
          compile_args = compile_args,
          install_args = install_args,
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

      if build_dir is not None and osp.exists(build_dir) and build.build_clean:
        self.logger.info(f"Removing build dir: {build_dir}")
        shutil.rmtree(build_dir)
