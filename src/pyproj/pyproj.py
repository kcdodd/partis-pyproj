import os
import os.path as osp
import sys
import shutil
import logging
import tempfile
from copy import copy, deepcopy
from collections.abc import (
  Mapping,
  Sequence )
import subprocess
import multiprocessing
import glob
import warnings
import tomli

try:
  from importlib.metadata import metadata

except ImportError:
  from importlib_metadata import metadata

from .pkginfo import (
  PkgInfoReq,
  PkgInfo )

from .validate import (
  ValidationWarning,
  ValidationError,
  FileOutsideRootError,
  valid_dict,
  validating,
  valid,
  restrict,
  mapget )

from .norms import (
  scalar_list,
  norm_bool,
  norm_path_to_os,
  norm_path )

from .pep import (
  purelib_compat_tags,
  platlib_compat_tags )

from .load_module import (
  EntryPointError,
  load_module,
  load_entrypoint )

from .legacy import legacy_setup_content

from .pptoml import (
  pptoml )

from .meson import (
  MesonBuild )

from .dist_file import (
  dist_copy )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class PyProjBase:
  """Minimal build system for a Python project

  Extends beyond :pep:`517` and :pep:`621`


  Parameters
  ----------
  root : str
    Path to the root project directory containing 'pyproject.toml'.
  logger : logging.Logger
    Parent logger to use when processing project.

  """
  #-----------------------------------------------------------------------------
  def __init__( self, *,
    root,
    config_settings = None,
    logger = None ):

    self.logger = logger or logging.getLogger( __name__ )

    self.root = osp.realpath(root)

    self.pptoml_file = osp.join( self.root, 'pyproject.toml' )

    with open( self.pptoml_file, 'rb' ) as fp:
      src = fp.read()
      src = src.decode( 'utf-8', errors = 'replace' )
      self._pptoml = tomli.loads( src )

    with validating(root = self._pptoml, file = self.pptoml_file):
      self._pptoml = pptoml(self._pptoml)

    #...........................................................................
    # construct a validator from the tool.pyproj.config table
    config_default = dict()

    for k,v in self.pyproj.config.items():
      if isinstance(v, bool):
        config_default[k] = valid(v, norm_bool)

      elif isinstance(v, scalar_list):
        config_default[k] = restrict(*v)

      else:
        config_default[k] = valid(v, type(v))

    class valid_config(valid_dict):
      _allow_keys = list()
      _default = config_default

    with validating( key = 'config_settings' ):
      _config_settings = valid_config(config_settings or dict())

      self.pyproj.config = _config_settings

    #...........................................................................
    self.build_backend = mapget( self.pptoml,
      'build-system.build-backend',
      "" )

    self.backend_path = mapget( self.pptoml,
      'build-system.backend-path',
      list() )

    #...........................................................................
    # default build requirements
    self.build_requires = self.pptoml.build_system.requires

    #...........................................................................
    # used to create name for binary distribution
    self.is_platlib = bool(self.binary.platlib.copy)

    if self.is_platlib:
      self.binary.compat_tags = platlib_compat_tags()

    #...........................................................................
    self.prep()

    with validating(key = 'project', root = self._pptoml, file = self.pptoml_file):
      self.pkg_info = PkgInfo(
        project = self.project,
        root = root )

    # Update logger once package info is created
    self.logger = self.logger.getChild( f"['{self.pkg_info.name_normed}']" )

  #-----------------------------------------------------------------------------
  @property
  def pptoml(self):
    """pptoml : Parsed and validated pyproject.toml document
    """
    return self._pptoml

  #-----------------------------------------------------------------------------
  @property
  def project(self):
    """:class:`partis.pyproj.pptoml.project`
    """
    return self._pptoml.project

  #-----------------------------------------------------------------------------
  @property
  def pyproj(self):
    """:class:`partis.pyproj.pptoml.pyproj`
    """
    return self._pptoml.tool.pyproj

  #-----------------------------------------------------------------------------
  @property
  def config(self):
    """:class:`partis.pyproj.pptoml.pyproj_config`
    """
    return self._pptoml.tool.pyproj.config

  #-----------------------------------------------------------------------------
  @property
  def meson(self):
    """:class:`partis.pyproj.pptoml.pyproj_meson`
    """
    return self._pptoml.tool.pyproj.meson

  #-----------------------------------------------------------------------------
  @property
  def dist(self):
    """:class:`partis.pyproj.pptoml.pyproj_dist`
    """
    return self._pptoml.tool.pyproj.dist

  #-----------------------------------------------------------------------------
  @property
  def source(self):
    """:class:`partis.pyproj.pptoml.pyproj_dist_source`
    """
    return self._pptoml.tool.pyproj.dist.source

  #-----------------------------------------------------------------------------
  @property
  def binary(self):
    """:class:`partis.pyproj.pptoml.pyproj_dist_binary`
    """
    return self._pptoml.tool.pyproj.dist.binary


  #-----------------------------------------------------------------------------
  @property
  def add_legacy_setup(self):
    """bool
    """
    return self.dist.source.add_legacy_setup

  #-----------------------------------------------------------------------------
  @property
  def build_requires(self):
    """set[:class:`PkgInfoReq`]
    """
    return self._build_requires

  #-----------------------------------------------------------------------------
  @build_requires.setter
  def build_requires(self, reqs):
    self._build_requires = set([ PkgInfoReq(r) for r in reqs ])

  #-----------------------------------------------------------------------------
  def prep_entrypoint( self, name, obj, logger ):

    prep = obj.get( 'prep', None )

    if not prep:
      return None

    prep_name = name

    entry_point = prep.entry
    entry_point_kwargs = prep.kwargs

    try:
      func = load_entrypoint(
        entry_point = entry_point,
        root = self.root )

      logger.info(f"loaded entry-point '{entry_point}'")

    except Exception as e:
      raise EntryPointError(f"failed to load entry-point '{entry_point}'") from e

    try:
      cwd = os.getcwd()

      with validating( file = f"{prep_name} -> {entry_point}(**{entry_point_kwargs})" ):
        func(
          self,
          logger = logger,
          **entry_point_kwargs )

    except Exception as e:
      raise EntryPointError(f"failed to run entry-point '{entry_point}'") from e

    finally:
      os.chdir(cwd)


  #-----------------------------------------------------------------------------
  def prep( self ):
    """Prepares project metadata
    """
    # backup project to detect changes made by prep
    project = deepcopy(self.project)
    dynamic = project.dynamic


    if dynamic and 'prep' not in self.pyproj:
      raise ValidationError(f"tool.pyproj.prep is required to resolve project.dynamic")

    self.prep_entrypoint(
      name = f"tool.pyproj.prep",
      obj = self.pyproj,
      logger = self.logger.getChild( f"prep" ) )

    # NOTE: check that any dynamic meta-data is defined after prep
    for k in dynamic:
      # all dynamic keys should updated by prep
      if k not in self.project or self.project[k] == project[k]:
        warnings.warn(
          f"project.dynamic listed key as dynamic, but not altered in prep: {k}",
          ValidationWarning )

    for k, v in self.project.items():
      if k not in dynamic and (k not in project or project[k] != v):
        # don't allow keys to be added or changed unless they were listed in dynamic
        raise ValidationError(
          f"prep updated key not listed in project.dynamic: {k}" )

    # fields are no longer dynamic
    self.project.dynamic = list()

    # make sure build requirements are still a set of PkgInfoReq
    self.build_requires = self.build_requires

  #-----------------------------------------------------------------------------
  def dist_prep( self ):
    """Prepares project files for a distribution
    """

    self.prep_entrypoint(
      name = f"tool.pyproj.dist.prep",
      obj = self.dist,
      logger = self.logger.getChild( f"dist.prep" ) )


  #-----------------------------------------------------------------------------
  def dist_source_prep( self ):
    """Prepares project files for a source distribution
    """

    self.prep_entrypoint(
      name = f"tool.pyproj.dist.source.prep",
      obj = self.dist.source,
      logger = self.logger.getChild( f"dist.source.prep" ) )

  #-----------------------------------------------------------------------------
  def dist_source_copy( self, *, dist ):
    """Copies prepared files into a source distribution

    Parameters
    ---------
    sdist : :class:`dist_base <partis.pyproj.dist_file.dist_base.dist_base>`
      Builder used to write out source distribution files
    """

    with validating( key = f'tool.pyproj.dist.source' ):
      dist_copy(
        base_path = dist.named_dirs['root'],
        include = self.source.copy,
        ignore = self.dist.ignore + self.source.ignore,
        dist = dist,
        root = self.root,
        logger = self.logger )

      if self.add_legacy_setup:
        with validating( key = f'add_legacy_setup' ):

          self.logger.info(f"generating legacy 'setup.py'")
          legacy_setup_content( self, dist )

  #-----------------------------------------------------------------------------
  def dist_binary_prep( self ):
    """Prepares project files for a binary distribution
    """

    with MesonBuild(
      root = self.root,
      meson = self.meson,
      logger = self.logger.getChild( f"meson" ) ):

      self.prep_entrypoint(
        name = f"tool.pyproj.dist.binary.prep",
        obj = self.binary,
        logger = self.logger.getChild( f"dist.binary.prep" ) )

    self.logger.debug(f"Compatibility tags after dist.binary.prep: {self.binary.compat_tags}")

  #-----------------------------------------------------------------------------
  def dist_binary_copy( self, *, dist ):
    """Copies prepared files into a binary distribution

    Parameters
    ---------
    bdist : :class:`dist_base <partis.pyproj.dist_file.dist_base.dist_base>`
      Builder used to write out binary distribution files
    """


    with validating( key = f'tool.pyproj.dist.binary' ):
      ignore = self.dist.ignore + self.dist.binary.ignore

      dist_copy(
        base_path = dist.named_dirs['root'],
        include = self.binary.copy,
        ignore = ignore,
        dist = dist,
        root = self.root,
        logger = self.logger )

      data_scheme = [
        'data',
        'headers',
        'scripts',
        'purelib',
        'platlib' ]

      for k in data_scheme:
        if k in self.binary:

          dist_data = self.binary[k]

          _include = dist_data.copy
          _ignore = ignore + dist_data.ignore

          with validating( key = k ):
            dist_copy(
              base_path = dist.named_dirs[k],
              include = _include,
              ignore = _ignore,
              dist = dist,
              root = self.root,
              logger = self.logger )
