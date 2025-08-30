from __future__ import annotations
from logging import (
  getLogger,
  Logger)
from copy import deepcopy
import subprocess
import warnings
import tomli
from pathlib import (
  Path)
from importlib import metadata

from .pkginfo import (
  PkgInfoReq,
  PkgInfo )
from .validate import (
  ValidationWarning,
  ValidationError,
  FileOutsideRootError,
  RequiredValueError,
  valid_dict,
  validating,
  valid,
  restrict,
  mapget )
from .norms import (
  scalar_list,
  norm_bool,
  hash_sha256)
from .pep import (
  platlib_compat_tags )
from .path import (
  resolve)
from .load_module import (
  EntryPoint )

from .legacy import legacy_setup_content

from .pptoml import (
  pptoml,
  project,
  pyproj,
  pyproj_dist,
  pyproj_dist_source,
  pyproj_dist_binary,
  pyproj_targets,
  # NOTE: deprecated
  pyproj,
  pyproj_meson,
  pyproj_targets)

from .builder import (
  Builder )

from .dist_file import (
  dist_copy )

#===============================================================================
class PyProjBase:
  """Minimal build system for a Python project

  Extends beyond :pep:`517` and :pep:`621`


  Parameters
  ----------
  root :
    Path to the root project directory containing 'pyproject.toml'.
  logger :
    Parent logger to use when processing project.

  """

  root: Path
  logger: Logger
  editable: bool
  pptoml_file: Path
  pptoml_checksum: tuple[str, int]
  commit: str
  env_pkgs: list[str]

  #-----------------------------------------------------------------------------
  def __init__( self, *,
    root: Path,
    config_settings: dict|None = None,
    logger: Logger|None = None,
    editable: bool = False):

    root = resolve(Path(root))

    self.root = root
    self.logger = logger or getLogger( __name__ )
    self.editable = editable

    self.pptoml_file = self.root / 'pyproject.toml'

    with open( self.pptoml_file, 'rb' ) as fp:
      src = fp.read()
      self.pptoml_checksum = hash_sha256(src)

      src = src.decode( 'utf-8', errors = 'replace' )
      self._pptoml = tomli.loads( src )

    with validating(root = self._pptoml, file = self.pptoml_file):
      self._pptoml = pptoml(self._pptoml)

      with validating(key = 'tool'):
        if 'tool' not in self.pptoml:
          # TODO: !!!
          raise RequiredValueError("tool.pyproj is required for backend")

        with validating(key = 'pyproj'):
          if 'pyproj' not in self.pptoml.tool:
            raise RequiredValueError("tool.pyproj is required for backend")

      if self.project.dynamic and 'prep' not in self.pyproj:
        raise RequiredValueError("tool.pyproj.prep is required to resolve project.dynamic")

    #...........................................................................
    # construct a validator from the tool.pyproj.config table
    # NOTE: only really used in the event that "config_settings" are passed to the backend
    config_default = dict()

    for k,v in self.pyproj.config.items():
      if isinstance(v, bool):
        config_default[k] = valid(v, norm_bool)

      elif isinstance(v, scalar_list):
        config_default[k] = restrict(*v)

      else:
        config_default[k] = valid(v, type(v))

    class valid_config_settings(valid_dict):
      allow_keys = list()
      default = config_default

    with validating( key = 'config_settings' ):
      self._config_settings = valid_config_settings(config_settings or dict())

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

    with validating(
      key = 'project',
      root = self._pptoml,
      file = self.pptoml_file):

      self.pkg_info = PkgInfo(
        project = self.project,
        root = self.root )

    # Update logger once package info is created
    self.logger = self.logger.getChild( f"['{self.pkg_info.name_normed}']" )

    # check if building from git repo
    commit = ''

    if (root/'.git').is_dir():
      commit = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()

    self.commit = commit

    # inspect/record the environment for installed packages
    self.env_pkgs = sorted(set([
      f"{pkg.metadata['Name']}=={pkg.metadata['Version']}"
      for pkg in metadata.Distribution.discover()]))

    # ensure that essential files will be in the source distribution
    essential = [
      Path('pyproject.toml'),
      self.project.get('readme', {}).get('file'),
      self.project.get('license', {}).get('file')]

    for file in essential:
      if not (file is None or any(c.src == file for c in self.source.copy)):
        self.source.copy.append(file)

  #-----------------------------------------------------------------------------
  @property
  def pptoml(self) -> pptoml:
    """pptoml : Parsed and validated pyproject.toml document
    """
    return self._pptoml

  #-----------------------------------------------------------------------------
  @property
  def project(self) -> project:
    """:class:`partis.pyproj.pptoml.project`
    """
    return self._pptoml.project

  #-----------------------------------------------------------------------------
  @property
  def pyproj(self) -> pyproj:
    return self._pptoml.tool.pyproj

  #-----------------------------------------------------------------------------
  @property
  def config_settings(self):
    """Config settings passed to backend, or defaults from ``pyproj.config``
    """
    return self._config_settings

  #-----------------------------------------------------------------------------
  # alias for backward compatibility
  config = config_settings

  #-----------------------------------------------------------------------------
  @property
  def targets(self) -> pyproj_targets:
    return self._pptoml.tool.pyproj.targets

  #-----------------------------------------------------------------------------
  @property
  def meson(self):
    """:class:`partis.pyproj.pptoml.pyproj_meson`

    .. deprecated:: 0.1.0
      Use :attr:`PyProjBase.targets` to access all build targets.
      These are no longer restricted to meson, but this attribute kept for backward
      compatability.

      Inplace changes to the returned object are not propagated back to the target
      configuration.

    """
    targets = self._pptoml.tool.pyproj.targets

    if not (len(targets) == 1 and targets[0].entry == 'partis.pyproj.builder:meson'):
      raise ValidationError("The 'meson' attribute is undefined for targets")

    meson = dict(targets[0])
    meson.pop('entry')
    meson.pop('work_dir')
    meson.pop('env')
    meson.pop('exclusive')
    meson['compile'] = meson.pop('enabled')
    return pyproj_meson(meson)

  #-----------------------------------------------------------------------------
  @property
  def dist(self) -> pyproj_dist:
    return self._pptoml.tool.pyproj.dist

  #-----------------------------------------------------------------------------
  @property
  def source(self) -> pyproj_dist_source:
    return self._pptoml.tool.pyproj.dist.source

  #-----------------------------------------------------------------------------
  @property
  def binary(self) -> pyproj_dist_binary:
    return self._pptoml.tool.pyproj.dist.binary

  #-----------------------------------------------------------------------------
  @property
  def add_legacy_setup(self):
    """bool
    """
    return self.dist.source.add_legacy_setup

  #-----------------------------------------------------------------------------
  @property
  def build_requires(self) -> set[PkgInfoReq]:
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

    entry_point = EntryPoint(
      pyproj = self,
      root = self.root,
      name = name,
      logger = logger,
      entry = prep.entry )

    entry_point(**prep.kwargs)

  #-----------------------------------------------------------------------------
  def prep( self ):
    """Prepares project metadata
    """
    # backup project to detect changes made by prep
    project = deepcopy(self.project)
    dynamic = project.dynamic

    self.prep_entrypoint(
      name = "tool.pyproj.prep",
      obj = self.pyproj,
      logger = self.logger.getChild("prep") )

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
      name = "tool.pyproj.dist.prep",
      obj = self.dist,
      logger = self.logger.getChild("dist.prep") )


  #-----------------------------------------------------------------------------
  def dist_source_prep( self ):
    """Prepares project files for a source distribution
    """

    self.prep_entrypoint(
      name = "tool.pyproj.dist.source.prep",
      obj = self.dist.source,
      logger = self.logger.getChild("dist.source.prep") )

  #-----------------------------------------------------------------------------
  def dist_source_copy( self, *, dist ):
    """Copies prepared files into a source distribution

    Parameters
    ---------
    sdist : :class:`dist_base <partis.pyproj.dist_file.dist_base.dist_base>`
      Builder used to write out source distribution files
    """

    with validating( key = 'tool.pyproj.dist.source'):
      dist_copy(
        base_path = dist.named_dirs['root'],
        copy_items = self.source.copy,
        ignore = self.dist.ignore + self.source.ignore,
        dist = dist,
        root = self.root,
        logger = self.logger )

      if self.add_legacy_setup:
        with validating(key = 'add_legacy_setup'):

          self.logger.info("generating legacy 'setup.py'")
          legacy_setup_content( self, dist )

  #-----------------------------------------------------------------------------
  def dist_binary_prep( self, incremental: bool = False ):
    """Prepares project files for a binary distribution
    """

    builder = Builder(
      pyproj = self,
      root = self.root,
      targets = self.targets,
      logger = self.logger.getChild("targets"),
      editable = self.editable)

    with builder:
      builder.build_targets()

      self.prep_entrypoint(
        name = "tool.pyproj.dist.binary.prep",
        obj = self.binary,
        logger = self.logger.getChild("dist.binary.prep") )

    self.logger.debug(f"Compatibility tags after dist.binary.prep: {self.binary.compat_tags}")

  #-----------------------------------------------------------------------------
  def dist_binary_copy( self, *, dist ):
    """Copies prepared files into a binary distribution

    Parameters
    ---------
    bdist : :class:`dist_base <partis.pyproj.dist_file.dist_base.dist_base>`
      Builder used to write out binary distribution files
    """


    with validating(key = 'tool.pyproj.dist.binary'):
      ignore = self.dist.ignore + self.dist.binary.ignore

      dist_copy(
        base_path = dist.named_dirs['root'],
        copy_items = self.binary.copy,
        ignore = ignore,
        dist = dist,
        root = self.root,
        logger = self.logger,
        follow_symlinks = True)

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
              copy_items = _include,
              ignore = _ignore,
              dist = dist,
              root = self.root,
              logger = self.logger,
              follow_symlinks = True)
