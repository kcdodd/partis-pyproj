from __future__ import annotations
from pathlib import (
  PurePosixPath)
from ..pep import (
  norm_dist_filename )
from ..pkginfo import PkgInfo
from .dist_base import dist_base
from .dist_targz import dist_targz

#===============================================================================
class dist_source_targz( dist_targz ):
  """Build a source distribution ``*.tar.gz`` file

  Parameters
  ----------
  pkg_info : :class:`PkgInfo <partis.pyproj.pkginfo.PkgInfo>`
  outdir : None | str | pathlib.Path
    Path to directory where the wheel file should be copied after completing build.
  tmpdir : None | str | pathlib.Path
    If not None, uses the given directory to place the temporary wheel file before
    copying to final location.
    My be the same as outdir.
  logger : None | :class:`logging.Logger`
    Logger to use.

  Example
  -------

  .. code-block:: python

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:

      import os
      import os.path

      pkg_dir = os.path.join( tmpdir, 'src', 'my_package' )
      out_dir = os.path.join( tmpdir, 'build' )

      os.makedirs( pkg_dir )

      with open( os.path.join( pkg_dir, 'module.py' ), 'w' ) as fp:
        fp.write("print('hello')")


      from partis.pyproj import (
        PkgInfo,
        dist_source_targz )

      pkg_info = PkgInfo(
        project = dict(
          name = 'my-package',
          version = '1.0' ) )

      with dist_source_targz(
        pkg_info = pkg_info,
        outdir = out_dir ) as sdist:

        sdist.copytree(
          src = './src',
          dst = os.path.join( sdist.base_path, 'src' ) )


  """
  #-----------------------------------------------------------------------------
  def __init__( self,
    pkg_info,
    outdir = None,
    tmpdir = None,
    logger = None ):

    if not isinstance( pkg_info, PkgInfo ):
      raise ValueError(f"pkg_info must be instance of PkgInfo: {pkg_info}")

    self.pkg_info = pkg_info

    sdist_name_parts = [
      norm_dist_filename( self.pkg_info.name_normed ),
      norm_dist_filename( self.pkg_info.version ) ]

    self.base_path = PurePosixPath('-'.join( sdist_name_parts ))

    self.metadata_path = self.base_path.joinpath('PKG-INFO')

    super().__init__(
      outname = '-'.join( sdist_name_parts ) + '.tar.gz',
      outdir = outdir,
      tmpdir = tmpdir,
      logger = logger,
      named_dirs = {
        'root' : self.base_path,
        'metadata' : self.metadata_path } )


  #-----------------------------------------------------------------------------
  def finalize( self ):

    self.write(
      dst = self.metadata_path,
      data = self.pkg_info.encode_pkg_info() )


#===============================================================================
class dist_source_dummy( dist_base ):
  """Build a dummy source distribution without a physical file
  """

  #-----------------------------------------------------------------------------
  def __init__( self,
    pkg_info,
    outdir = None,
    tmpdir = None,
    logger = None ):

    if not isinstance( pkg_info, PkgInfo ):
      raise ValueError(f"pkg_info must be instance of PkgInfo: {pkg_info}")

    self.pkg_info = pkg_info

    sdist_name_parts = [
      self.pkg_info.name_normed,
      self.pkg_info.version ]

    self.base_path = PurePosixPath('-'.join( sdist_name_parts ))

    self.metadata_path = self.base_path.joinpath('PKG-INFO')

    super().__init__(
      outname = '-'.join( sdist_name_parts ) + '.tar.gz',
      outdir = outdir,
      tmpdir = tmpdir,
      logger = logger,
      named_dirs = {
        'root' : self.base_path,
        'metadata' : self.metadata_path } )


  #-----------------------------------------------------------------------------
  def create_distfile( self ): # pragma: no cover
    pass

  #-----------------------------------------------------------------------------
  def close_distfile( self ): # pragma: no cover
    pass

  #-----------------------------------------------------------------------------
  def copy_distfile( self ): # pragma: no cover
    pass

  #-----------------------------------------------------------------------------
  def remove_distfile( self ): # pragma: no cover
    pass

  #-----------------------------------------------------------------------------
  def finalize( self ): # pragma: no cover
    pass
