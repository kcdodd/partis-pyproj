import os
import os.path as osp
import io
import warnings
import stat

import tempfile
import shutil
import tarfile

from .dist_base import dist_base

from ..norms import (
  norm_path,
  norm_data,
  norm_mode )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class dist_targz( dist_base ):
  """Builds a tar-file  with gz compression

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
        dist_targz )

      with dist_targz(
        outname = 'my_dist.tar.gz',
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
    self._tarfile = None

  #-----------------------------------------------------------------------------
  def create_distfile( self ):

    ( self._fd, self._tmp_path ) = tempfile.mkstemp(
      dir = self.tmpdir )

    self._fp = os.fdopen( self._fd, "w+b" )

    self._tarfile = tarfile.open(
      fileobj = self._fp,
      mode = 'w:gz',
      format = tarfile.PAX_FORMAT )


  #-----------------------------------------------------------------------------
  def close_distfile( self ):

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

  #-----------------------------------------------------------------------------
  def finalize( self ): # pragma: no cover
    pass

  #-----------------------------------------------------------------------------
  def exists( self,
    dst ):

    self.assert_open()

    try:
      self._tarfile.getmember(dst)
      return True
    except KeyError as e:
      return False
