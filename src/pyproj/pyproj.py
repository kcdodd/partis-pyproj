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

from .norms import (
  norm_path_to_os,
  norm_path,
  valid_type,
  valid_keys,
  mapget,
  as_list,
  CompatibilityTags,
  ValidationError )

from .load_module import (
  load_module,
  load_entrypoint )

from .legacy import legacy_setup_content

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
    logger = None ):

    self.logger = logger or logging.getLogger( __name__ )

    self.root = osp.abspath(root)

    self.pptoml_file = osp.join( self.root, 'pyproject.toml' )

    with open( self.pptoml_file, 'rb' ) as fp:
      src = fp.read()
      src = src.decode( 'utf-8', errors = 'replace' )
      self.pptoml = tomli.loads( src )

    #...........................................................................
    valid_keys(
      name = 'pyproject.toml',
      obj = self.pptoml,
      require_keys = [
        'project',
        'tool' ],
      allow_keys = [
        'build-system' ] )

    #...........................................................................
    tool = self.pptoml['tool']

    valid_keys(
      name = 'tool',
      obj = tool,
      require_keys = [
        'pyproj' ] )

    #...........................................................................
    self.pyproj = tool['pyproj']

    valid_keys(
      name = 'tool.pyproj',
      obj = self.pyproj,
      allow_keys = [
        'prep',
        'dist',
        'meson' ] )

    #...........................................................................
    self.dist = mapget( self.pyproj, 'dist', dict() )

    valid_keys(
      name = 'tool.pyproj.dist',
      obj = self.dist,
      allow_keys = [
        'prep',
        'ignore',
        'source',
        'binary' ] )

    self.dist_source = mapget( self.dist, 'source', dict() )
    self.dist_binary = mapget( self.dist, 'binary', dict() )

    valid_keys(
      name = 'tool.pyproj.dist.source',
      obj = self.dist_source,
      allow_keys = [
        'prep',
        'ignore',
        'copy',
        'add_legacy_setup' ] )

    self.add_legacy_setup = self.dist_source.get('add_legacy_setup', False )

    valid_keys(
      name = 'tool.pyproj.dist.binary',
      obj = self.dist_binary,
      allow_keys = [
        'prep',
        'ignore',
        'copy',
        'data',
        'headers',
        'scripts',
        'purelib',
        'platlib' ] )

    self.is_platlib = bool( mapget( self.dist_binary, 'platlib.copy', list() ) )

    #...........................................................................
    self.meson = mapget( self.pyproj, 'meson', dict() )

    valid_keys(
      name = 'tool.pyproj.meson',
      obj = self.meson,
      allow_keys = [
        'compile',
        'src_dir',
        'build_dir',
        'prefix',
        'setup_args',
        'compile_args',
        'install_args',
        'options' ] )

    self.meson.setdefault('src_dir', '.' )
    self.meson.setdefault('build_dir', 'build')
    self.meson.setdefault('prefix', 'build')
    self.meson.setdefault('compile', False)

    self.meson.setdefault('setup_args', list())
    self.meson.setdefault('compile_args', list())
    self.meson.setdefault('install_args', list())

    self.meson.setdefault('options', dict())

    self.meson['src_dir'] = osp.join(
      self.root,
      norm_path_to_os(self.meson['src_dir'] ) )

    self.meson['build_dir'] = osp.join(
      self.root,
      norm_path_to_os(self.meson['build_dir']) )

    self.meson['prefix'] = osp.join(
      self.root,
      norm_path_to_os(self.meson['prefix'] ) )

    #...........................................................................
    self.build_backend = mapget( self.pptoml,
      'build-system.build-backend',
      "" )

    self.backend_path = mapget( self.pptoml,
      'build-system.backend-path',
      list() )

    #...........................................................................
    self.build_requires = set([
      PkgInfoReq(r)
      for r in mapget( self.pptoml, 'build-system.requires', list() ) ])

    if self.meson['compile']:
      v = metadata('partis-pyproj')['Version']

      self.build_requires.add( PkgInfoReq(f'partis-pyproj[meson] == {v}') )

    #...........................................................................
    self.project = self.pptoml['project']

    valid_keys(
      name = 'project',
      obj = self.project,
      require_keys = [
        'name' ])

    self.prep()

    self.pkg_info = PkgInfo(
      project = self.project,
      root = root )

    # Update logger once package info is created
    self.logger = self.logger.getChild( f"['{self.pkg_info.name_normed}']" )

  #-----------------------------------------------------------------------------
  def prep_entrypoint( self, name, obj, logger ):

    prep = obj.get( 'prep', None )

    if not prep:
      return None

    prep_name = name

    valid_keys(
      name = prep_name,
      obj = prep,
      require_keys = [
        'entry' ],
      allow_keys = [
        'kwargs' ] )

    entry_point = prep['entry']
    entry_point_kwargs = prep.get('kwargs', dict() )


    func = load_entrypoint(
      entry_point = entry_point,
      root = self.root )

    logger.info(f"loaded entry-point '{entry_point}'")

    try:
      cwd = os.getcwd()

      res = func(
        self,
        logger = logger,
        **entry_point_kwargs )

      return res

    finally:
      os.chdir(cwd)

  #-----------------------------------------------------------------------------
  def meson_build( self ):

    #...........................................................................
    if self.meson['compile']:

      for dir in [ self.meson['build_dir'], self.meson['prefix'] ]:
        if not osp.exists(dir):
          os.makedirs(dir)

      meson_build_dir = tempfile.mkdtemp(
        dir = self.meson['build_dir'] )

      meson_out_dir = self.meson['prefix']

      self.logger.info(f"Running meson build")
      self.logger.info(f"Meson tmp: {meson_build_dir}")
      self.logger.info(f"Meson out: {meson_out_dir}")

      setup_args = [
        'meson',
        'setup',
        *self.meson['setup_args'],
        '--prefix',
        meson_out_dir,
        *[ f'-D{k}={v}' for k,v in self.meson['options'].items() ],
        meson_build_dir,
        self.meson['src_dir'] ]

      compile_args = [
        'meson',
        'compile',
        *self.meson['compile_args'],
        '-C',
        meson_build_dir ]

      install_args = [
        'meson',
        'install',
        *self.meson['install_args'],
        '--no-rebuild',
        '-C',
        meson_build_dir ]


      self.logger.debug(' '.join(setup_args))

      subprocess.check_call(setup_args)

      self.logger.debug(' '.join(compile_args))

      subprocess.check_call(compile_args)

      self.logger.debug(' '.join(install_args))

      subprocess.check_call(install_args)

  #-----------------------------------------------------------------------------
  def prep( self ):
    """Prepares project metadata
    """
    # backup project to detect changes made by prep
    project = deepcopy(self.project)
    dynamic = project.get( 'dynamic', list() )

    if 'name' in dynamic:
      raise ValidationError(f"project.dynamic may not contain 'name'")

    if dynamic and 'prep' not in self.pyproj:
      raise ValidationError(f"tool.pyproj.prep is required to resolve project.dynamic")

    _project = self.prep_entrypoint(
      name = f"tool.pyproj.prep",
      obj = self.pyproj,
      logger = self.logger.getChild( f"prep" ) )

    if _project is not None:

      if not isinstance( _project, Mapping ):
        raise ValidationError(
          f"tool.pyproj.prep must return a mapping: {type(_project)}" )

      self.project.update(_project)

    # NOTE: return value treated as update to project, but if self.project
    # was modified directly it needs to be checked anyway
    for k in dynamic:
      # require all dynamic keys are updated by prep
      if k not in self.project or (k in project and project[k] == self.project[k]):
        raise ValidationError(
          f"project.dynamic listed key as dynamic not updated from prep: {k}" )

    for k, v in self.project.items():
      if (k not in project or project[k] != v) and k not in dynamic:
        # don't allow keys to be updated unless they were listed in dynamic
        raise ValidationError(
          f"prep updated key not listed in project.dynamic: {k}" )

    # fields are no longer dynamic
    self.project['dynamic'] = list()

  #-----------------------------------------------------------------------------
  def dist_prep( self ):
    """Prepares project files for a distribution
    """

    return self.prep_entrypoint(
      name = f"tool.pyproj.dist.prep",
      obj = self.dist,
      logger = self.logger.getChild( f"dist.prep" ) )


  #-----------------------------------------------------------------------------
  def dist_source_prep( self ):
    """Prepares project files for a source distribution
    """

    return self.prep_entrypoint(
      name = f"tool.pyproj.dist.source.prep",
      obj = self.dist_source,
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

    include = list( mapget( self.dist_source, 'copy', list() ) )

    ignore = (
      mapget( self.dist, 'ignore', list() )
      + mapget( self.dist_source, 'ignore', list() ) )

    self.dist_copy(
      name = name,
      base_path = dist.named_dirs['root'],
      include = include,
      ignore = ignore,
      dist = dist )

    if self.add_legacy_setup:
      self.logger.info(f"generating legacy 'setup.py'")
      legacy_setup_content( self, dist )


  #-----------------------------------------------------------------------------
  def dist_binary_prep( self ):
    """Prepares project files for a binary distribution
    """

    self.meson_build()

    compat_tags = self.prep_entrypoint(
      name = f"tool.pyproj.dist.binary.prep",
      obj = self.dist_binary,
      logger = self.logger.getChild( f"dist.binary.prep" ) )

    if compat_tags:
      self.logger.debug(f"Compatibility tags returned from dist.binary.prep: {compat_tags}")

      compat_tags = as_list(compat_tags)

      compat_tags = [
        CompatibilityTags(*tags)
        for tags in compat_tags ]

    elif self.is_platlib:
      from packaging.tags import sys_tags

      tag = next(iter(sys_tags()))

      # interpreter = "py{0}{1}".format(sys.version_info.major, sys.version_info.minor)
      interpreter = tag.interpreter

      compat_tags = [ CompatibilityTags( interpreter, tag.abi, tag.platform ) ]

      self.logger.debug(f"Compatibility tags assumed: {compat_tags}")

    return compat_tags

  #-----------------------------------------------------------------------------
  def dist_binary_copy( self, *, dist ):
    """Copies prepared files into a binary distribution

    Parameters
    ---------
    bdist : :class:`dist_base <partis.pyproj.dist_file.dist_base.dist_base>`
      Builder used to write out binary distribution files
    """

    name = f'tool.pyproj.dist.binary'

    include = list( mapget( self.dist_binary, 'copy', list() ) )

    ignore = (
      mapget( self.dist, 'ignore', list() )
      + mapget( self.dist_binary, 'ignore', list() ) )

    self.dist_copy(
      name = name,
      base_path = dist.named_dirs['root'],
      include = include,
      ignore = ignore,
      dist = dist )

    data_scheme = [
      'data',
      'headers',
      'scripts',
      'purelib',
      'platlib' ]

    for k in data_scheme:
      if k in self.dist_binary:
        name = f'tool.pyproj.dist.binary.{k}'

        dist_data = mapget( self.dist_binary, k, dict() )

        valid_keys(
          name = name,
          obj = dist_data,
          allow_keys = [
            'ignore',
            'copy' ] )

        _include = list( mapget( dist_data, 'copy', list() ) )

        _ignore = (
          ignore
          + mapget( dist_data, 'ignore', list() ) )

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
        if ignore and src in ignore('.', [src]):
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

      _ignore_patterns = ignore_patterns

      typ = valid_type(
        name = incl_name,
        obj = incl,
        types = [ str, Mapping ] )

      if typ is str:
        yield ( incl, incl, _ignore_patterns )

      else:
        valid_keys(
          name = incl_name,
          obj = incl,
          min_keys = [
            ('src', 'glob') ],
          allow_keys = [
            'dst',
            'ignore' ])

        _ignore = as_list( incl.get( 'ignore', list() ) )
        _ignore_patterns = shutil.ignore_patterns(*(ignore + _ignore)) if _ignore else _ignore_patterns

        src = incl.get('src', '')
        dst = incl.get('dst', src)

        if 'glob' in incl:
          _glob = osp.join(src, incl['glob'])

          for _src in glob.iglob(_glob, recursive = True):
            _dst = osp.join( dst, osp.relpath(_src, start = src) )

            yield ( _src, _dst, _ignore_patterns )

        else:

          yield ( src, dst, _ignore_patterns )
