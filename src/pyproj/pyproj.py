import os
import os.path as osp
import sys
import shutil
import logging
import tempfile
from copy import copy
from collections.abc import (
  Mapping,
  Sequence )

import tomli

from .pkginfo import (
  PkgInfoReq,
  PkgInfo )

from .norms import (
  allowed_keys,
  mapget )

from .load_module import (
  load_module )

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

    if logger is None:
      logger = logging.getLogger( __name__ )

    self.root = str(root)

    self.pptoml_file = osp.join( self.root, 'pyproject.toml' )

    with open( self.pptoml_file, 'r' ) as fp:
      self.pptoml = tomli.loads( fp.read() )

    if 'project' not in self.pptoml:
      raise ValueError(
        f"'project' metadata must be minimally defined: {pptoml_file}")

    self.pkg_info = PkgInfo(
      project = self.pptoml.get( 'project' ),
      root = root )

    # Update logger once package info is created
    self.logger = logger.getChild( f"['{self.pkg_info.name_normed}']" )

    self.pyproj = mapget( self.pptoml, 'tool.pyproj', None )

    if not self.pyproj:
      raise ValueError(
        f"[tool.pyproj] must be minimally defined for this backend: {pptoml_file}")


    if not self.pyproj:
      raise ValueError(
        f"'tool.pyproj' must be minimally defined for this backend: {pptoml_file}")

    allowed_keys(
      name = 'tool.pyproj',
      obj = self.pyproj,
      keys = [
        'dist',
        'sdist',
        'bdist',
        'external',
        'sub_projects' ] )

    self.dist = mapget( self.pyproj, 'dist', dict() )

    allowed_keys(
      name = 'tool.pyproj.dist',
      obj = self.dist,
      keys = [
        'ignore',
        'source',
        'binary' ] )

    self.dist_source = mapget( self.dist, 'source', dict() )
    self.dist_binary = mapget( self.dist, 'binary', dict() )


    allowed_keys(
      name = 'tool.pyproj.dist.source',
      obj = self.dist_source,
      keys = [
        'prep',
        'ignore',
        'copy',
        'add_legacy_setup' ] )

    allowed_keys(
      name = 'tool.pyproj.dist.binary',
      obj = self.dist_binary,
      keys = [
        'prep',
        'ignore',
        'copy',
        'top_level',
        'data',
        'headers',
        'scripts',
        'purelib',
        'platlib' ] )

    self.top_level = mapget( self.dist_binary, 'top_level', list() )

    self.sub_projects = [
      type(self)(
        root = osp.join( root, subdir ),
        logger = self.logger )
      for subdir in mapget( self.pyproj, 'sub_projects', list() ) ]

    self.build_backend = mapget( self.pptoml,
        'build-system.build-backend',
        "" )

    self.backend_path = mapget( self.pptoml,
        'build-system.backend-path',
        list() )


    self.build_requires = set([
      PkgInfoReq(r)
      for r in mapget( self.pptoml, 'build-system.requires', list() ) ])

    for sub_proj in self.sub_projects:
      self.pkg_info = self.pkg_info.provides( sub_proj.pkg_info )
      self.build_requires |= sub_proj.build_requires

    # filter out any dependencies listing the one being provided
    # NOTE: this dose not do any checking of version, up to repo maintainers
    self.build_requires = set([
      r
      for r in self.build_requires
      if r.req.name not in self.pkg_info._provides_dist ])

  #-----------------------------------------------------------------------------
  def dist_source_prep( self ):
    """Prepares project files for a source distribution
    """

    _cwd = os.getcwd()

    for sub_proj in self.sub_projects:
      try:
        os.chdir( sub_proj.root )
        sub_proj.dist_source_prep()

      finally:
        os.chdir(_cwd)

    prep = mapget( self.dist_source, 'prep', dict() )
    prep_name = f"tool.pyproj.dist.source.prep"

    allowed_keys(
      name = prep_name,
      obj = prep,
      keys = [
        'entry',
        'kwargs' ] )

    entry_point = mapget( prep, 'entry', '' )
    entry_point_kwargs = mapget( prep, 'kwargs', dict() )

    if entry_point:
      mod_name, func_name = entry_point.split(':')

      mod = load_module(
        path = mod_name,
        root = self.root )

      if not hasattr( mod, func_name ):
        raise ValueError(
          f"{prep_name}.entry '{func_name}' not found in module '{mod_name}'" )

      func = getattr( mod, func_name )

      self.logger.info(f"{prep_name}: {entry_point}")

      func( self, **entry_point_kwargs )

  #-----------------------------------------------------------------------------
  def dist_source_copy( self, *, dist ):
    """Copies prepared files into a source distribution

    Parameters
    ---------
    sdist : :class:`dist_base <partis.pyproj.dist_file.dist_base.dist_base>`
      Builder used to write out source distribution files
    """

    _cwd = os.getcwd()

    for sub_proj in self.sub_projects:
      try:
        os.chdir( sub_proj.root )
        sub_proj.dist_source_copy(
          dist = dist )

      finally:
        os.chdir(_cwd)

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

    if mapget( self.dist_source, 'add_legacy_setup', False ):
      self.logger.info(f"generating legacy 'setup.py'")
      legacy_setup_content( self, sdist )


  #-----------------------------------------------------------------------------
  def dist_binary_prep( self ):
    """Prepares project files for a binary distribution
    """

    _cwd = os.getcwd()

    for sub_proj in self.sub_projects:
      try:
        os.chdir( sub_proj.root )
        sub_proj.dist_binary_prep()

      finally:
        os.chdir(_cwd)

    prep = mapget( self.dist_binary, 'prep', dict() )
    prep_name = f"tool.pyproj.dist.binary.prep"

    allowed_keys(
      name = prep_name,
      obj = prep,
      keys = [
        'entry',
        'kwargs' ] )

    entry_point = mapget( prep, 'entry', '' )
    entry_point_kwargs = mapget( prep, 'kwargs', dict() )

    if entry_point:
      mod_name, func_name = entry_point.split(':')

      mod = load_module(
        path = mod_name,
        root = self.root )

      if not hasattr( mod, func_name ):
        raise ValueError(
          f"{prep_name}.entry '{func_name}' not found in module '{mod_name}'" )

      func = getattr( mod, func_name )

      self.logger.info(f"{prep_name}: {entry_point}")

      func( self, **entry_point_kwargs )

  #-----------------------------------------------------------------------------
  def dist_binary_copy( self, *, dist ):
    """Copies prepared files into a binary distribution

    Parameters
    ---------
    bdist : :class:`dist_base <partis.pyproj.dist_file.dist_base.dist_base>`
      Builder used to write out binary distribution files
    """

    _cwd = os.getcwd()

    for sub_proj in self.sub_projects:
      try:
        os.chdir( sub_proj.root )
        sub_proj.dist_binary_copy(
          dist = dist )

      finally:
        os.chdir(_cwd)

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

        allowed_keys(
          name = name,
          obj = dist_data,
          keys = [
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

    include = copy(include)
    ignore_patterns = shutil.ignore_patterns(*ignore) if len(ignore) > 0 else None

    for i, incl in enumerate(include):
      incl_name = f'{name}.copy[{i}]'

      _ignore_patterns = ignore_patterns

      if isinstance( incl, str ):
        include[i] = ( incl, incl, _target, _ignore_patterns )

      elif isinstance( incl, Mapping ):
        allowed_keys(
          name = incl_name,
          obj = incl,
          keys = [
            'src',
            'dst',
            'ignore' ] )

        if 'src' not in incl:
          raise ValueError(
            f'{incl_name} must have a `src`:{incl}')

        if 'dst' not in incl:
          incl['dst'] = incl['src']

        if 'ignore' in incl:
          _ignore = incl['ignore']

          if isinstance( _ignore, str ):
            _ignore = [ _ignore, ]

          if len(_ignore) > 0:
            _ignore_patterns = shutil.ignore_patterns( *( ignore + _ignore ) )

        include[i] = ( incl['src'], incl['dst'], _ignore_patterns )

      else:
        raise ValueError(
          f"{incl_name} must be a string [from/to], or mapping {{src = 'from', dst = 'to'}}: {incl}")

    for src, dst, ignore in include:

      src = osp.normpath( src )
      dst = osp.normpath( osp.join( base_path, dst ) )

      self.logger.info(f"dist copy: {src} -> {dst}")

      if osp.isdir( src ):
        dist.copytree(
          src = src,
          dst = dst,
          ignore = ignore )

      else:
        dist.copyfile(
          src = src,
          dst = dst )
