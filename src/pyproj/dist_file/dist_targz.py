from __future__ import annotations
import os
from pathlib import (
  Path,
  PurePosixPath)
import io
import tempfile
import shutil
import tarfile
from .dist_base import dist_base
from ..norms import (
  norm_path,
  norm_data,
  norm_mode )

#===============================================================================
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

    tmpdir = Path(tmpdir) if tmpdir else None

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

    self._tmp_path = Path(self._tmp_path)

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
    if not self._tmp_path:
      return

    # overwiting in destination directory
    if self.outpath.exists():
      # NOTE: the missing_ok parameter was not added until py38
      self.outpath.unlink()

    self.outdir.mkdir(parents = True, exist_ok = True)
    shutil.copyfile( self._tmp_path, self.outpath )

  #-----------------------------------------------------------------------------
  def remove_distfile( self ):
    if not self._tmp_path:
      return

    # remove temporary file
    if self._tmp_path.exists():
      self._tmp_path.unlink()

    self._tmp_path = None

  #-----------------------------------------------------------------------------
  def write( self,
    dst: PurePosixPath,
    data: bytes,
    mode: int|None = None,
    exist_ok: bool = False,
    record: bool = True):

    self.assert_open()

    dst = norm_path(dst)
    data = norm_data(data)

    if record:
      rec = self.record(
        dst = dst,
        data = data,
        exist_ok = exist_ok)

      if rec is None:
        # equivalent file has already been added
        return

    elif not exist_ok and self.exists( dst ):
      # NOTE: can only skip equivalent files when they are recorded
      raise ValueError(f"Overwriting destination: {dst}")

    info = tarfile.TarInfo(dst)

    info.size = len(data)
    info.mode = norm_mode( mode )

    self._tarfile.addfile(
      info,
      fileobj = io.BytesIO(data) )

  #-----------------------------------------------------------------------------
  def write_link( self,
    dst: PurePosixPath,
    target: PurePosixPath,
    mode: int|None = None,
    exist_ok: bool = False,
    record: bool = True):

    self.assert_open()
    dst = norm_path(dst)
    target = norm_path(target, parent_ok = True)
    self.logger.debug(f"write_link {dst} ({target})")

    data = target.encode('utf-8')

    if record:
      rec = self.record(
        dst = dst,
        data = data,
        exist_ok = exist_ok)

      if rec is None:
        # equivalent file has already been added
        return

    elif not exist_ok and self.exists( dst ):
      # NOTE: can only skip equivalent files when they are recorded
      raise ValueError(f"Overwriting destination: {dst}")

    info = tarfile.TarInfo(dst)
    info.type = tarfile.SYMTYPE
    info.linkname = target
    self._tarfile.addfile(info)

  #-----------------------------------------------------------------------------
  def finalize( self ): # pragma: no cover
    pass

  #-----------------------------------------------------------------------------
  def exists( self,
    dst ):

    self.assert_open()

    try:
      self._tarfile.getmember(os.fspath(dst))
      return True
    except KeyError as e:
      return False
