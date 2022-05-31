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
import tomli

try:
  from importlib.metadata import metadata

except ImportError:
  from importlib_metadata import metadata

from .pkginfo import (
  PkgInfoReq,
  PkgInfo )

from .validate import (
  ValidationError,
  valid_dict,
  validating,
  valid,
  mapget )

from .norms import (
  norm_bool,
  norm_path_to_os,
  norm_path )

from .pep import (
  purelib_compat_tags,
  platlib_compat_tags )

from .load_module import (
  load_module,
  load_entrypoint )

from .legacy import legacy_setup_content

from .pptoml import (
  pptoml )


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class PyProjBase:
  """Minimal build system for a Python project

  Extends beyond PEP 517 :cite:`pep0517` and 621 :cite:`pep0621`.


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

    if config_settings:
      # construct a validator from the tool.pyproj.config table
      config_default = dict()

      for k,v in self.pyproj.config.items():
        if isinstance(v, bool):
          config_default[k] = valid(v, norm_bool)
        else:
          config_default[k] = valid(v, type(v))

      class config(valid_dict):
        _allow_keys = list()
        _default = config_default

      with validating( key = 'config_settings' ):
        config_settings = config(config_settings)

        self.pyproj.config.update(config_settings)

    #...........................................................................
    self.build_backend = mapget( self.pptoml,
      'build-system.build-backend',
      "" )

    self.backend_path = mapget( self.pptoml,
      'build-system.backend-path',
      list() )

    #...........................................................................
    # default build requirements
    self.build_requires = set([
      PkgInfoReq(r)
      for r in mapget( self.pptoml, 'build-system.requires', list() ) ])

    if self.pyproj.meson['compile']:
      try:
        metadata('meson')
      except:
        v = metadata('partis-pyproj')['Version']

        self.build_requires.add( PkgInfoReq(f'partis-pyproj[meson] == {v}') )


    #...........................................................................
    # used to create name for binary distribution
    self.is_platlib = bool(self.binary.platlib.copy)

    if self.is_platlib:
      self.binary.compat_tags = platlib_compat_tags()
    else:
      self.binary.compat_tags = purelib_compat_tags()

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
    return self._pptoml

  #-----------------------------------------------------------------------------
  @property
  def project(self):
    return self._pptoml.project

  #-----------------------------------------------------------------------------
  @property
  def pyproj(self):
    return self._pptoml.tool.pyproj

  #-----------------------------------------------------------------------------
  @property
  def config(self):
    return self._pptoml.tool.pyproj.config

  #-----------------------------------------------------------------------------
  @property
  def meson(self):
    return self._pptoml.tool.pyproj.meson

  #-----------------------------------------------------------------------------
  @property
  def dist(self):
    return self._pptoml.tool.pyproj.dist

  #-----------------------------------------------------------------------------
  @property
  def binary(self):
    return self._pptoml.tool.pyproj.dist.binary

  #-----------------------------------------------------------------------------
  @property
  def source(self):
    return self._pptoml.tool.pyproj.dist.source

  #-----------------------------------------------------------------------------
  @property
  def add_legacy_setup(self):
    return self.dist.source.add_legacy_setup

  #-----------------------------------------------------------------------------
  def prep_entrypoint( self, name, obj, logger ):

    prep = obj.get( 'prep', None )

    if not prep:
      return None

    prep_name = name

    entry_point = prep['entry']
    entry_point_kwargs = prep.get('kwargs', dict() )

    if not entry_point:
      return None


    try:
      func = load_entrypoint(
        entry_point = entry_point,
        root = self.root )

      logger.info(f"loaded entry-point '{entry_point}'")

    except Exception as e:
      raise ValueError(f"failed to load entry-point '{entry_point}'") from e

    try:
      cwd = os.getcwd()

      with validating( file = entry_point ):
        func(
          self,
          logger = logger,
          **entry_point_kwargs )

    except Exception as e:
      raise ValueError(f"failed to run entry-point '{entry_point}'") from e

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
      # require all dynamic keys are updated by prep
      if k not in self.project:
        raise ValidationError(
          f"project.dynamic listed key as dynamic, but not updated in prep: {k}" )

    for k, v in self.project.items():
      if k not in dynamic and (k not in project or project[k] != v):
        # don't allow keys to be added or changed unless they were listed in dynamic
        raise ValidationError(
          f"prep updated key not listed in project.dynamic: {k}" )

    # fields are no longer dynamic
    self.project.dynamic = list()

    # make sure build requirements are still a set of PkgInfoReq
    self.build_requires = set([
      PkgInfoReq(r)
      for r in self.build_requires ])

  #-----------------------------------------------------------------------------
  def meson_compile( self ):

    #...........................................................................
    if not self.meson.compile:
      return

    # check paths
    meson_paths = dict()

    for k in ['src_dir', 'build_dir', 'prefix']:

      rel_path = norm_path_to_os(self.meson[k])

      if osp.isabs(rel_path):
        raise ValidationError(f"tool.pyproj.meson.{k} must be relative to pyproject.toml: {rel_path}")

      abs_path = osp.realpath( osp.join(
        self.root,
        rel_path ) )

      if osp.commonprefix([self.root, abs_path]) != self.root:
        raise ValidationError(f"tool.pyproj.meson.{k} must resolve to a project directory: {abs_path}")

      meson_paths[k] = abs_path


    for dir in [ meson_paths['build_dir'], meson_paths['prefix'] ]:
      if not osp.exists(dir):
        os.makedirs(dir)

    meson_build_dir = tempfile.mkdtemp(
      dir = meson_paths['build_dir'] )

    meson_prefix = meson_paths['prefix']

    self.logger.info(f"Running meson build")
    self.logger.info(f"Meson build dir: {meson_build_dir}")
    self.logger.info(f"Meson prefix: {meson_prefix}")

    def meson_option_arg(k, v):
      if isinstance(v, bool):
        v = ({True: 'true', False: 'false'})[v]

      return f'-D{k}={v}'

    # TODO: ensure any paths in setup_args are normalized

    setup_args = [
      'meson',
      'setup',
      *self.meson.setup_args,
      '--prefix',
      meson_prefix,
      *[ meson_option_arg(k,v) for k,v in self.meson.options.items() ],
      meson_build_dir,
      meson_paths['src_dir'] ]

    compile_args = [
      'meson',
      'compile',
      *self.meson.compile_args,
      '-C',
      meson_build_dir ]

    install_args = [
      'meson',
      'install',
      *self.meson.install_args,
      '--no-rebuild',
      '-C',
      meson_build_dir ]


    self.logger.debug(' '.join(setup_args))

    subprocess.check_call(setup_args)

    self.logger.debug(' '.join(compile_args))

    subprocess.check_call(compile_args)

    self.logger.debug(' '.join(install_args))

    subprocess.check_call(install_args)

    if self.meson.build_clean:
      self.logger.info(f"Cleaning Meson build dir: {meson_build_dir}")
      shutil.rmtree(meson_build_dir)

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

    name = f'tool.pyproj.dist.source'

    self.dist_copy(
      name = name,
      base_path = dist.named_dirs['root'],
      include = self.source.copy,
      ignore = self.dist.ignore + self.source.ignore,
      dist = dist )

    if self.add_legacy_setup:
      self.logger.info(f"generating legacy 'setup.py'")
      legacy_setup_content( self, dist )

  #-----------------------------------------------------------------------------
  def dist_binary_prep( self ):
    """Prepares project files for a binary distribution
    """

    self.meson_compile()

    self.prep_entrypoint(
      name = f"tool.pyproj.dist.binary.prep",
      obj = self.binary,
      logger = self.logger.getChild( f"dist.binary.prep" ) )

    if not self.binary.compat_tags:
      raise ValidationError(f"At least one set of binary compatability tags is required: {self.binary}")

    self.logger.debug(f"Compatibility tags after dist.binary.prep: {self.binary.compat_tags}")

  #-----------------------------------------------------------------------------
  def dist_binary_copy( self, *, dist ):
    """Copies prepared files into a binary distribution

    Parameters
    ---------
    bdist : :class:`dist_base <partis.pyproj.dist_file.dist_base.dist_base>`
      Builder used to write out binary distribution files
    """

    name = f'tool.pyproj.dist.binary'

    ignore = self.dist.ignore + self.dist.binary.ignore

    self.dist_copy(
      name = name,
      base_path = dist.named_dirs['root'],
      include = self.binary.copy,
      ignore = ignore,
      dist = dist )

    data_scheme = [
      'data',
      'headers',
      'scripts',
      'purelib',
      'platlib' ]

    for k in data_scheme:
      if k in self.binary:
        name = f'tool.pyproj.dist.binary.{k}'

        dist_data = self.binary[k]

        _include = dist_data.copy
        _ignore = ignore + dist_data.ignore

        self.dist_copy(
          name = name,
          base_path = dist.named_dirs[k],
          include = _include,
          ignore = _ignore,
          dist = dist )

  #-----------------------------------------------------------------------------
  def dist_copy( self, *,
    name,
    base_path,
    include,
    ignore,
    dist ):

    if len(include) == 0:
      return

    for src, dst, ignore in self.dist_iter(name, include, ignore):

      src = osp.normpath( src )
      dst = '/'.join( [base_path, norm_path(dst)] )

      self.logger.info(f"dist copy: {src} -> {dst}")

      if osp.isdir( src ):
        dist.copytree(
          src = src,
          dst = dst,
          ignore = ignore )

      else:
        if ignore and ignore('.', [src]):
          continue

        dist.copyfile(
          src = src,
          dst = dst )

  #-----------------------------------------------------------------------------
  def dist_iter( self,
    name,
    include,
    ignore ):

    ignore_patterns = shutil.ignore_patterns(*ignore) if ignore else None

    for i, incl in enumerate(include):
      incl_name = f'{name}.copy[{i}]'

      _ignore = incl.ignore
      _ignore_patterns = shutil.ignore_patterns(*(ignore + _ignore)) if _ignore else ignore_patterns

      src = incl.src
      dst = incl.dst

      if incl.glob:
        _glob = osp.join(src, incl.glob)

        for _src in glob.iglob(_glob, recursive = True):
          _dst = osp.join( dst, osp.relpath(_src, start = src) )

          yield ( _src, _dst, _ignore_patterns )

      else:

        yield ( src, dst, _ignore_patterns )
