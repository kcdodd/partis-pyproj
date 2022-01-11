import os
import os.path as osp
import io
import stat
import logging

from .norms import (
  hash_sha256 )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_base:
  """
  Parameters
  ----------
  outname : str
    Name of output file.
  outdir : str
    Path to directory where the file should be copied after completing build.
  tmpdir : None | str
    If not None, uses the given directory to place the temporary file(s) before
    copying to final location.
    May be the same as outdir.
  logger : None | logging.Logger

  Attributes
  ----------
  outpath : str
    Path to output file
  opened : bool
    Build temp file has been opened for writing
  finalized : bool
    Output file has been finalized.
  closed : bool
    Build temp file has been closed
  copied : bool
    Output file has been copied to 'outpath' location

  See Also
  --------

  """
  #-----------------------------------------------------------------------------
  def __init__( self,
    outname,
    outdir = None,
    tmpdir = None,
    logger = None ):

    if outdir is None:
      outdir = os.getcwd()

    if logger is None:
      logger = logging.getLogger( type(self).__name__ )

    self.outname = str(outname)
    self.outdir = str(outdir)
    self.outpath = osp.join( self.outdir, self.outname )
    self.tmpdir = str(tmpdir) if tmpdir else None
    self.logger = logger

    self.records = list()
    self.record_bytes = None
    self.record_hash = None

    self.opened = False
    self.finalized = False
    self.closed = False
    self.copied = False

  #-----------------------------------------------------------------------------
  def make_buildfile( self ):
    """Must be implemented
    """
    raise NotImplementedError('')

  #-----------------------------------------------------------------------------
  def close_buildfile( self ):
    """Must be implemented
    """
    raise NotImplementedError('')

  #-----------------------------------------------------------------------------
  def finalize( self ):
    """Must be implemented
    """
    raise NotImplementedError('')

  #-----------------------------------------------------------------------------
  def copy_buildfile( self ):
    """Must be implemented
    """
    raise NotImplementedError('')

  #-----------------------------------------------------------------------------
  def remove_buildfile( self ):
    """Must be implemented
    """
    raise NotImplementedError('')

  #-----------------------------------------------------------------------------
  def assert_open( self ):
    if self.opened and not self.closed:
      return

    raise ValueError("build file is not open")

  #-----------------------------------------------------------------------------
  def assert_recordable( self ):
    self.assert_open()

    if not self.finalized:
      return

    raise ValueError("build record has already been finalized.")


  #-----------------------------------------------------------------------------
  def open( self ):
    if self.opened:
      raise ValueError("build file has already been opened")

    self.logger.info( f'building {self.outname}' )

    try:

      self.make_buildfile()

      self.opened = True

      return self

    except:
      self.close(
        finalize = False,
        copy = False )

      raise

  #-----------------------------------------------------------------------------
  def record( self,
    dst,
    data ):
    """
    """

    self.assert_recordable()

    hash, size = hash_sha256( data )

    record = ( dst, hash, size )

    self.logger.debug( 'record ' + str(record) )

    self.records.append( record )

  #-----------------------------------------------------------------------------
  def close( self,
    finalize = True,
    copy = True ):

    if self.closed:
      return

    if finalize and not self.finalized:
      self.logger.info( f'finalizing {self.outname}' )
      self.finalize()
      self.finalized = True

    self.close_buildfile()
    self.closed = True

    if copy and not self.copied:
      self.logger.info( f'copying {self.outname}' )
      self.copy_buildfile()
      self.copied = True

  #-----------------------------------------------------------------------------
  def exists( self,
    dst ):
    """Behaviour similar to os.path.exists for entries in the build file

    Parameters
    ----------
    dst : str | path

    Returns
    -------
    exists : bool
    """
    return False

  #-----------------------------------------------------------------------------
  def write( self,
    dst,
    data,
    mode = None,
    record = True ):
    """Write data into the build file

    Parameters
    ----------
    dst : str | path
    data : bytes
    mode : int
    exist_ok : bool
    record : bool
      Add all file to the record

    """

    if record:
      self.record(
        dst = dst,
        data = data )

  #-----------------------------------------------------------------------------
  def makedirs( self,
    dst,
    mode = None,
    exist_ok = False,
    record = True ):
    """Behaviour similar to os.makedirs into the build file

    Parameters
    ----------
    dst : str | path
    mode : int
    exist_ok : bool
    record : bool
      Add all files to the record

    NOTES
    -----
    Some archive file types do not need to explicitly create directories, but this
    is given in case an implementation needs to create a directory before creating
    files within the directory.

    """

    if not exist_ok and self.exists( dst ):
      raise ValueError(f"Build file already has entry: {dst}")

  #-----------------------------------------------------------------------------
  def copyfile( self,
    src,
    dst,
    mode = None,
    record = True ):
    """Behaviour similar to shutil.copyfile into the build file

    Parameters
    ----------
    src : str | path
    dst : str | path
    record : bool
      Add all files to the RECORD
    """

    if self.exists( dst ):
      raise ValueError(f"Build file already has entry: {dst}")

    self.logger.debug( f'copyfile {src}' )

    if mode is None:
      mode = os.stat( src ).st_mode

    with open( src, "rb" ) as fp:
      self.write(
        dst = dst,
        data = fp,
        mode = mode,
        record = record )

    return dst

  #-----------------------------------------------------------------------------
  def copytree( self,
    src,
    dst,
    ignore = None,
    record = True ):
    """Behaviour similar to shutil.copytree into the build file

    Parameters
    ----------
    src : str | path
    dst : str | path
    ignore : None | callable
      If not None, ``callable(src, names) -> ignored_names``

      See :func:`shutil.copytree`
    record : bool
      Add all files to the RECORD
    """

    self.logger.debug( f'copytree {src}' )

    entries = list( os.scandir( src ) )

    if ignore is not None:
      ignored_names = ignore(
        os.fspath( src ),
        [ x.name for x in entries ] )

      if len(ignored_names) > 0:
        self.logger.debug( f'ignoring {ignored_names}' )

        entries = [ entry
          for entry in entries
          if entry.name not in ignored_names ]

    for entry in entries:
      src_path = os.path.join( src, entry.name )
      dst_path = os.path.join( dst, entry.name )

      mode = entry.stat().st_mode

      if entry.is_dir():

        self.makedirs(
          dst = dst_path,
          mode = mode,
          record = record )

        self.copytree(
          src = src_path,
          dst = dst_path,
          ignore = ignore,
          record = record )

      else:

        self.copyfile(
          src = src_path,
          dst = dst_path,
          mode = mode,
          record = record )

    return dst

  #-----------------------------------------------------------------------------
  def __enter__(self):

    return self.open()

  #-----------------------------------------------------------------------------
  def __exit__(self, type, value, traceback ):

    # only finalize if there was not an error
    no_error = ( type is None )

    self.close(
      finalize = no_error,
      copy = no_error )

    # don't handle any errors here
    return None
