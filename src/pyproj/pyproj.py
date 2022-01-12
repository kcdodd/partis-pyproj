import os
import os.path as osp
import sys
import shutil
import logging
import tempfile

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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class PyProjBase:
  """A minimal interface for a Python project extending beyond PEP 517 and 621


  Parameters
  ----------
  root : str
    Path to the root project directory containing 'pyproject.toml'.

  See Also
  --------
  `https://www.python.org/dev/peps/pep-0621/`_
  """
  #-----------------------------------------------------------------------------
  def __init__( self,
    root,
    logger = None ):

    if logger is None:
      logger = logging.getLogger( type(self).__name__ )

    self.root = str(root)
    self.logger = logger

    self.pptoml_file = osp.join( self.root, 'pyproject.toml' )

    with open( self.pptoml_file, 'r' ) as fp:
      self.pptoml = tomli.loads( fp.read() )

    if 'project' not in self.pptoml:
      raise ValueError(
        f"'project' metadata must be minimally defined: {pptoml_file}")

    self.tool_partis = mapget( self.pptoml, 'tool.partis', None )

    if not self.tool_partis:
      raise ValueError(
        f"'tool.partis' must be minimally defined for this backend: {pptoml_file}")

    allowed_keys(
      name = 'tool.partis',
      obj = self.tool_partis,
      keys = [
        'pyproj' ] )

    self.pyproj = mapget( self.tool_partis, 'pyproj', None )

    if not self.pyproj:
      raise ValueError(
        f"'tool.partis.pyproj' must be minimally defined for this backend: {pptoml_file}")

    allowed_keys(
      name = 'tool.partis.pyproj',
      obj = self.pyproj,
      keys = [
        'dist',
        'sdist',
        'bdist',
        'external',
        'sub_projects' ] )

    self.dist = mapget( self.pyproj, 'dist', dict() )

    allowed_keys(
      name = 'tool.partis.pyproj.dist',
      obj = self.dist,
      keys = [
        'any',
        'source',
        'binary' ] )

    self.dist_any = mapget( self.dist, 'any', dict() )
    self.dist_source = mapget( self.dist, 'source', dict() )
    self.dist_binary = mapget( self.dist, 'binary', dict() )

    allowed_keys(
      name = 'tool.partis.pyproj.dist.any',
      obj = self.dist_any,
      keys = [
        'ignore' ] )

    allowed_keys(
      name = 'tool.partis.pyproj.dist.source',
      obj = self.dist_source,
      keys = [
        'prep',
        'ignore',
        'copy' ] )

    allowed_keys(
      name = 'tool.partis.pyproj.dist.binary',
      obj = self.dist_binary,
      keys = [
        'prep',
        'ignore',
        'copy',
        'top_level' ] )

    self.top_level = mapget( self.dist_binary, 'top_level', list() )

    self.sub_projects = [
      type(self)(
        root = osp.join( root, subdir ),
        logger = self.logger )
      for subdir in mapget( self.pyproj, 'sub_projects', list() ) ]

    self.pkg_info = PkgInfo(
      project = mapget( self.pptoml, 'project', dict() ),
      root = root )

    self.build_requires = set([
      PkgInfoReq(r)
      for r in mapget( self.pptoml, 'build-system.requires', list() ) ])

    for sub_proj in self.sub_projects:
      self.pkg_info.extend( sub_proj.pkg_info )
      self.build_requires |= sub_proj.build_requires

    # filter out any dependencies listing the one being provided
    # NOTE: this dose not do any checking of version, up to repo maintainers
    self.build_requires = set([
      r
      for r in self.build_requires
      if r.req.name not in self.pkg_info._provides_dist ])

  #-----------------------------------------------------------------------------
  def dist_source_prep( self ):
    _cwd = os.getcwd()

    for sub_proj in self.sub_projects:
      try:
        os.chdir( sub_proj.root )
        sub_proj.dist_source_prep()

      finally:
        os.chdir(_cwd)

    prep = mapget( self.dist_source, 'prep', dict() )
    prep_name = f"tool.partis.pyproj.dist.source.prep"

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
  def dist_source_copy( self, sdist ):

    _cwd = os.getcwd()

    for sub_proj in self.sub_projects:
      try:
        os.chdir( sub_proj.root )
        sub_proj.dist_source_copy(
          sdist = sdist )

      finally:
        os.chdir(_cwd)

    ignore = (
      mapget( self.dist_any, 'ignore', list() )
      + mapget( self.dist_source, 'ignore', list() ) )

    ignore_patterns = shutil.ignore_patterns(*ignore) if len(ignore) > 0 else None

    includes = list( mapget( self.dist_source, 'copy', list() ) )

    for i, incl in enumerate(includes):
      incl_name = f'tool.partis.pyproj.dist.source.copy[{i}]'

      if isinstance( incl, str ):
        includes[i] = ( incl, incl )

      elif isinstance( incl, Mapping ):
        allowed_keys(
          name = incl_name,
          obj = incl,
          keys = [
            'src',
            'dst' ] )

        includes[i] = ( incl['src'], incl['dst'] )

      else:
        raise ValueError(
          f"{incl_name} must be a string [from/to], or mapping {{src = [from], dst = [to]}}: {incl}")

    for src, dst in includes:
      src = osp.normpath( src )
      dst = osp.normpath( osp.join( sdist.base_path, self.root, dst ) )

      self.logger.info(f"sdist copy: {src} -> {dst}")

      if osp.isdir( src ):
        sdist.copytree(
          src = src,
          dst = dst,
          ignore = ignore_patterns )

      else:
        sdist.copyfile(
          src = src,
          dst = dst )


  #-----------------------------------------------------------------------------
  def dist_binary_prep( self ):
    _cwd = os.getcwd()

    for sub_proj in self.sub_projects:
      try:
        os.chdir( sub_proj.root )
        sub_proj.dist_binary_prep()

      finally:
        os.chdir(_cwd)

    prep = mapget( self.dist_binary, 'prep', dict() )
    prep_name = f"tool.partis.pyproj.dist.binary.prep"

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
  def dist_binary_copy( self, bdist ):

    _cwd = os.getcwd()

    for sub_proj in self.sub_projects:
      try:
        os.chdir( sub_proj.root )
        sub_proj.dist_binary_copy(
          bdist = bdist )

      finally:
        os.chdir(_cwd)

    ignore = (
      mapget( self.dist_any, 'ignore', list() )
      + mapget( self.dist_binary, 'ignore', list() ) )

    ignore_patterns = shutil.ignore_patterns(*ignore) if len(ignore) > 0 else None

    includes = list( mapget( self.dist_binary, 'copy', list() ) )

    for i, incl in enumerate(includes):
      incl_name = f'tool.partis.pyproj.dist.binary.copy[{i}]'

      if isinstance( incl, str ):
        includes[i] = ( incl, incl )

      elif isinstance( incl, Mapping ):
        allowed_keys(
          name = incl_name,
          obj = incl,
          keys = [
            'src',
            'dst' ] )

        includes[i] = ( incl['src'], incl['dst'] )

      else:
        raise ValueError(
          f"{incl_name} must be a string [from/to], or mapping {{src = [from], dst = [to]}}: {incl}")

    for src, dst in includes:
      src = osp.normpath( src )
      dst = osp.normpath( dst )

      self.logger.info(f"bdist copy: {src} -> {dst}")

      if osp.isdir( src ):
        bdist.copytree(
          src = src,
          dst = dst,
          ignore = ignore_patterns )

      else:
        bdist.copyfile(
          src = src,
          dst = dst )
