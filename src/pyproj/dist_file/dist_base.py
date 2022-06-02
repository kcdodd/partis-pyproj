import os
import os.path as osp
import io
import stat
import logging
from abc import(
  ABC,
  abstractmethod )

from ..norms import (
  hash_sha256 )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class dist_base( ABC ):
  """Builder for file distribution

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
  named_dirs : None | Dict[ str, str ]
    Mapping of specially named directories within the distribution.
    By default a named directory { 'root' : '.' } will be added,
    unless overridden with another directory name.
  logger : None | logging.Logger
    Logger to which any status information is to be logged.

  Attributes
  ----------
  outpath : str
    Path to final output file location
  named_dirs : Dict[ str, str ]
    Mapping of specially named directories within the distribution
  opened : bool
    Build temporary file has been opened for writing
  finalized : bool
    Build temporary file has been finalized.
  closed : bool
    Build temporary file has been closed
  copied : bool
    Build temporary has been copied to ``outpath`` location
  records : List[ Tuple[ str, str, int ] ]
    Recorded list of path, hash, and size (bytes) of files added to distribution
  record_hash : None | str
    Final hash value of the record after being finalized

    .. note::

      Not all distribution implementations will create a hash of the record

  """
  #-----------------------------------------------------------------------------
  def __init__( self,
    outname,
    outdir = None,
    tmpdir = None,
    logger = None,
    named_dirs = None ):

    if outdir is None:
      outdir = os.getcwd()

    if logger is None:
      logger = logging.getLogger( type(self).__name__ )

    if named_dirs is None:
      named_dirs = dict()

    self.outname = str(outname)
    self.outdir = str(outdir)
    self.outpath = osp.join( self.outdir, self.outname )
    self.tmpdir = str(tmpdir) if tmpdir else None
    self.logger = logger
    self.named_dirs = {
      'root' : '.',
      **named_dirs }

    self.records = list()
    self.record_bytes = None
    self.record_hash = None

    self.opened = False
    self.finalized = False
    self.closed = False
    self.copied = False

  #-----------------------------------------------------------------------------
  def exists( self,
    dst ):
    """Behaviour similar to os.path.exists for entries in the distribution file

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
    """Write data into the distribution file

    Parameters
    ----------
    dst : str | path
    data : bytes
    mode : int
    record : bool
      Add file to the record

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
    """Behaviour similar to os.makedirs into the distribution file

    Parameters
    ----------
    dst : str | path
    mode : int
    exist_ok : bool
    record : bool
      Add file to the record

    Note
    ----
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
    exist_ok = False,
    record = True ):
    """Behaviour similar to shutil.copyfile into the distribution file

    Parameters
    ----------
    src : str | path
    dst : str | path
    mode : int
    exist_ok : bool
    record : bool
      Add file to the RECORD
    """

    if not osp.exists( src ):
      raise ValueError(f"Source file not found: {src}")

    if not exist_ok and self.exists( dst ):
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
    exist_ok = False,
    record = True ):
    """Behaviour similar to shutil.copytree into the distribution file

    Parameters
    ----------
    src : str | path
    dst : str | path
    ignore : None | callable

      If not None, ``callable(src, names) -> ignored_names``

      See :func:`shutil.copytree`
    exist_ok : bool
    record : bool
      Add all files to the RECORD
    """

    if not osp.exists( src ):
      raise ValueError(f"Source directory not found: {src}")

    self.logger.debug( f'copytree {src}' )

    entries = list( os.scandir( src ) )

    if ignore is not None:
      ignored_names = ignore(
        src,
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
          # TODO: separate option for existing directories? like `dirs_exist_ok`
          exist_ok = True,
          record = record )

        self.copytree(
          src = src_path,
          dst = dst_path,
          ignore = ignore,
          exist_ok = exist_ok,
          record = record )

      else:

        self.copyfile(
          src = src_path,
          dst = dst_path,
          mode = mode,
          exist_ok = exist_ok,
          record = record )

    return dst



  #-----------------------------------------------------------------------------
  def open( self ):
    """Opens the temporary distribution file

    Returns
    -------
    self : :class:`dist_base <partis.pyproj.dist_base.dist_base>`
    """

    if self.opened:
      raise ValueError("distribution file has already been opened")

    self.logger.info( f'building {self.outname}' )

    try:

      self.create_distfile()

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
    """Creates a record for an added file

    This produces an sha256 hash of the data and associates a record with the item

    Parameters
    ----------
    dst : str
      Path of item within the distribution
    data : bytes
      Binary data that was added

    Returns
    -------
    None
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
    """Closes the temporary distribution file

    Parameters
    ----------
    finalize : bool
      If true, finalizes the temporary distribution file before closing
    copy : bool
      If true, copies the temporary file to final location after closing

    Returns
    -------
    None
    """

    if self.closed:
      return

    if finalize and not self.finalized:
      self.logger.info( f'finalizing {self.outname}' )
      self.finalize()
      self.finalized = True

    self.close_distfile()
    self.closed = True

    if copy and not self.copied:
      self.logger.info( f'copying {self.outname} -> {self.outdir}' )
      self.copy_distfile()
      self.copied = True

    self.remove_distfile()

  #-----------------------------------------------------------------------------
  def __enter__(self):
    """Opens the temporary distribution file upon entering the context

    Returns
    -------
    self : :class:`dist_base <partis.pyproj.dist_base.dist_base>`
    """
    if self.opened:
      return self

    return self.open()

  #-----------------------------------------------------------------------------
  def __exit__(self, type, value, traceback ):
    """Closes the temporary distribution file upon exiting the context

    If no exception occured in the context, then the temporary distribution is finalized
    and copied to it's final locations
    """

    # only finalize if there was not an error
    no_error = ( type is None )

    self.close(
      finalize = no_error,
      copy = no_error )

    # don't handle any errors here
    return None

  #-----------------------------------------------------------------------------
  def assert_open( self ):
    """Raises exception if temporary file is not open
    """
    if self.opened and not self.closed:
      return

    raise ValueError("distribution file is not open")

  #-----------------------------------------------------------------------------
  def assert_recordable( self ):
    """Raises exception if temporary file has already been finalized
    """
    self.assert_open()

    if not self.finalized:
      return

    raise ValueError("distribution record has already been finalized.")

  #-----------------------------------------------------------------------------
  @abstractmethod
  def create_distfile( self ):
    """Creates and opens a temporary distribution file into which files are copied
    """
    raise NotImplementedError('')

  #-----------------------------------------------------------------------------
  @abstractmethod
  def finalize( self ):
    """Finalizes the distribution file before being closed

    Returns
    -------
    record_hash : None | str
      sha256 hash of the record

    Note
    ----
    Not all distribution implementations will create/return a hash of the record
    """
    raise NotImplementedError('')

  #-----------------------------------------------------------------------------
  @abstractmethod
  def close_distfile( self ):
    """Closes the temporary distribution file
    """
    raise NotImplementedError('')

  #-----------------------------------------------------------------------------
  @abstractmethod
  def copy_distfile( self ):
    """Copies the temporary distribution file to it's final location
    """
    raise NotImplementedError('')

  #-----------------------------------------------------------------------------
  @abstractmethod
  def remove_distfile( self ):
    """Deletes the temporary distribution file
    """
    raise NotImplementedError('')
