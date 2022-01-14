import os
import os.path as osp
import io
import warnings
import stat

import shutil

from ..norms import (
  norm_path,
  norm_data,
  norm_mode )

from ..pkginfo import PkgInfo

from .build_targz import build_targz

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_sdist_targz( build_targz ):
  """Build a source distribution ``*.tar.gz`` file

  Parameters
  ----------
  pkg_info : :class:`PkgInfo <partis.pyproj.pkginfo.PkgInfo>`
  outdir : str
    Path to directory where the wheel file should be copied after completing build.
  tmpdir : None | :class:`str`
    If not None, uses the given directory to place the temporary wheel file before
    copying to final location.
    My be the same as outdir.
  logger : None | :class:`logging.Logger`
    Logger to use.

  Examples
  --------

  .. testcode::

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
        build_sdist_targz )

      pkg_info = PkgInfo(
        project = dict(
          name = 'my-package',
          version = '1.0' ) )

      with build_sdist_targz(
        pkg_info = pkg_info,
        outdir = out_dir ) as sdist:

        sdist.copytree(
          src = './src',
          dst = os.path.join( sdist.base_path, 'src' ) )

      print( sdist.outname )
      print( os.path.relpath( sdist.outpath, tmpdir ) )

  .. testoutput::

    my-package-1.0.tar.gz
    build/my-package-1.0.tar.gz


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

    self.base_path = '-'.join( sdist_name_parts )

    self.metadata_path = self.base_path + '/PKG-INFO'

    super().__init__(
      outname = '-'.join( sdist_name_parts ) + '.tar.gz',
      outdir = outdir,
      tmpdir = tmpdir,
      logger = logger )


  #-----------------------------------------------------------------------------
  def finalize( self ):

    self.write(
      dst = self.metadata_path,
      data = self.pkg_info.encode_pkg_info() )
