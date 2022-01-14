import os
import os.path as osp
import io
import warnings
import stat

import tempfile
import shutil
import tarfile

from .build_base import build_base

from ..norms import (
  norm_path,
  norm_data,
  norm_mode )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_targz( build_base ):

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
    self._tarfile = None

  #-----------------------------------------------------------------------------
  def make_buildfile( self ):

    ( self._fd, self._tmp_path ) = tempfile.mkstemp(
      dir = self.tmpdir )

    self._fp = os.fdopen( self._fd, "w+b" )

    self._tarfile = tarfile.open(
      fileobj = self._fp,
      mode = 'w:gz',
      format = tarfile.PAX_FORMAT )


  #-----------------------------------------------------------------------------
  def close_buildfile( self ):

    if self._tarfile is not None:

      # close the file
      self._tarfile.close()
      self._tarfile = None

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

    if not osp.exists( self.outdir ):
      os.makedirs( self.outdir )

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

    info = tarfile.TarInfo( dst )

    info.size = len(data)
    info.mode = norm_mode( mode )

    self._tarfile.addfile(
      info,
      fileobj = io.BytesIO(data) )

    super().write(
      dst = dst,
      data = data,
      mode = mode,
      record = record )
