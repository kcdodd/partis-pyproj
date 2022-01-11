import os
import os.path as osp
import io
import warnings
import stat

import tempfile
import shutil
import zipfile

from .build_base import build_base

from .norms import (
  norm_path,
  norm_data,
  norm_mode,
  mode_to_xattr )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_zip( build_base ):
  """
  Parameters
  ----------

  See Also
  --------

  """
  #-----------------------------------------------------------------------------
  def __init__( self,
    outname,
    outdir = None,
    tmpdir = None,
    logger = None ):

    super().__init__(
      outname = outname,
      outdir = outdir,
      tmpdir = tmpdir,
      logger = logger )

    self._fd = None
    self._fp = None
    self._tmp_path = None
    self._zipfile = None
    
  #-----------------------------------------------------------------------------
  def make_buildfile( self ):

    ( self._fd, self._tmp_path ) = tempfile.mkstemp(
      dir = self.tmpdir )

    self._fp = os.fdopen( self._fd, "w+b" )

    self._zipfile = zipfile.ZipFile(
      self._fp,
      mode = "w",
      compression = zipfile.ZIP_DEFLATED )

  #-----------------------------------------------------------------------------
  def close_buildfile( self ):

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
  def copy_buildfile( self ):

    if osp.exists( self.outpath ):
      # overwiting in destination directory
      os.remove( self.outpath )

    shutil.copyfile( self._tmp_path, self.outpath )


  #-----------------------------------------------------------------------------
  def remove_buildfile( self ):

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

    zinfo.external_attr = mode_to_xattr( mode )

    self._zipfile.writestr(
      zinfo,
      data,
      compress_type = zipfile.ZIP_DEFLATED )

    super().write(
      dst = dst,
      data = data,
      mode = mode,
      record = record )
