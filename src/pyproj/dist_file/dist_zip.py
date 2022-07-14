import os
import os.path as osp
import io
import warnings
import stat

import tempfile
import shutil
import zipfile

from .dist_base import dist_base

from ..norms import (
  norm_path,
  norm_data,
  norm_mode,
  norm_zip_external_attr )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class dist_zip( dist_base ):
  """Builds a zip file

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
        dist_zip )

      with dist_zip(
        outname = 'my_dist.zip',
        outdir = out_dir ) as dist:

        dist.copytree(
          src = pkg_dir,
          dst = 'my_package' )

  """

  #-----------------------------------------------------------------------------
  def __init__( self,
    outname,
    outdir = None,
    tmpdir = None,
    named_dirs = None,
    logger = None ):

    super().__init__(
      outname = outname,
      outdir = outdir,
      tmpdir = tmpdir,
      named_dirs = named_dirs,
      logger = logger )

    self._fd = None
    self._fp = None
    self._tmp_path = None
    self._zipfile = None

  #-----------------------------------------------------------------------------
  def create_distfile( self ):

    ( self._fd, self._tmp_path ) = tempfile.mkstemp(
      dir = self.tmpdir )

    self._fp = os.fdopen( self._fd, "w+b" )

    self._zipfile = zipfile.ZipFile(
      self._fp,
      mode = "w",
      compression = zipfile.ZIP_DEFLATED )

  #-----------------------------------------------------------------------------
  def close_distfile( self ):

    if self._zipfile is not None:

      # close the file
      self._zipfile.close()
      self._zipfile = None

    if self._fp is not None:
      self._fp.close()
      self._fp = None

    if self._fd is not None:
      self._fd = None

  #-----------------------------------------------------------------------------
  def copy_distfile( self ):

    if osp.exists( self.outpath ):
      # overwiting in destination directory
      os.remove( self.outpath )

    if not osp.exists( self.outdir ):
      os.makedirs( self.outdir )

    shutil.copyfile( self._tmp_path, self.outpath )


  #-----------------------------------------------------------------------------
  def remove_distfile( self ):

    # remove temporary file
    os.remove( self._tmp_path )

    self._tmp_path = None

  #-----------------------------------------------------------------------------
  def write( self,
    dst,
    data,
    mode = None,
    record = True ):

    self.assert_open()

    dst = norm_path( dst )

    data = norm_data( data )

    zinfo = zipfile.ZipInfo( dst )

    zinfo.external_attr = norm_zip_external_attr( mode )

    self._zipfile.writestr(
      zinfo,
      data,
      compress_type = zipfile.ZIP_DEFLATED )

    super().write(
      dst = dst,
      data = data,
      mode = mode,
      record = record )

  #-----------------------------------------------------------------------------
  def finalize( self ): # pragma: no cover
    pass

  #-----------------------------------------------------------------------------
  def exists( self,
    dst ):

    self.assert_open()

    try:
      self._zipfile.getinfo(dst)
      return True
    except KeyError as e:
      return False
