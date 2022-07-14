import os
import os.path as osp
import io
import warnings
import stat

import tempfile
import shutil

from ..norms import (
  norm_path,
  norm_data,
  hash_sha256,
  email_encode_items )

from ..pep import (
  norm_dist_name,
  norm_dist_build,
  norm_dist_compat,
  compress_dist_compat,
  norm_dist_filename )

from ..pkginfo import PkgInfo

from .dist_zip import dist_zip

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def pkg_name(dir):
  if dir.endswith('.py'):
    return dir[:-3]

  return dir

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class dist_binary_wheel( dist_zip ):
  """Build a binary distribution :pep:`427`, :pep:`491` wheel file ``*.whl``

  Parameters
  ----------
  pkg_info : :class:`PkgInfo <partis.pyproj.pkginfo.PkgInfo>`
  build : str
    Build tag. Must start with a digit, or be an empty string.
  compat : List[ Tuple[str,str,str] ] | List[ :class:`CompatibilityTags <partis.pyproj.norms.CompatibilityTags>` ]
    List of build compatability tuples of the form ( py_tag, abi_tag, plat_tag ).
    e.g. ( 'py3', 'abi3', 'linux_x86_64' )
  outdir : str
    Path to directory where the wheel file should be copied after completing build.
  tmpdir : None | str
    If not None, uses the given directory to place the temporary wheel file before
    copying to final location.
    My be the same as outdir.
  logger : None | :class:`logging.Logger`
    Logger to use.
  gen_name : str
    Name to use as the 'Generator' of the wheel file

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
        dist_binary_wheel )

      pkg_info = PkgInfo(
        project = dict(
          name = 'my-package',
          version = '1.0' ) )


      with dist_binary_wheel(
        pkg_info = pkg_info,
        outdir = out_dir ) as bdist:

        bdist.copytree(
          src = pkg_dir,
          dst = 'my_package' )

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0427
  * https://www.python.org/dev/peps/pep-0491
  * https://www.python.org/dev/peps/pep-0660

  """
  #-----------------------------------------------------------------------------
  def __init__( self, *,
    pkg_info,
    build = '',
    compat = None,
    outdir = None,
    tmpdir = None,
    logger = None,
    gen_name = None ):

    if not compat:
      compat = [ ( 'py3', 'none', 'any' ), ]

    if not isinstance( pkg_info, PkgInfo ):
      raise ValueError(f"pkg_info must be instance of PkgInfo: {pkg_info}")

    self.pkg_info = pkg_info

    if gen_name is None:
      gen_name = f'{type(self).__module__}.{type(self).__name__}'

    self.build = norm_dist_build( build )

    self.compat = [
      norm_dist_compat( py_tag, abi_tag, plat_tag )
      for py_tag, abi_tag, plat_tag in compat ]

    self.top_level = list()
    self.purelib = True
    self.gen_name = str(gen_name)

    wheel_name_parts = [
      self.pkg_info.name_normed,
      self.pkg_info.version,
      self.build,
      *compress_dist_compat( self.compat ) ]

    wheel_name_parts = [
      norm_dist_filename(p)
      for p in wheel_name_parts
      if p != '' ]

    self.base_path = '-'.join( wheel_name_parts[:2] )
    self.base_tag = '-'.join( wheel_name_parts[-3:] )

    self.dist_info_path = self.base_path + '.dist-info'
    self.metadata_path = self.dist_info_path + '/METADATA'
    self.entry_points_path = self.dist_info_path + '/entry_points.txt'
    self.wheel_path = self.dist_info_path + '/WHEEL'
    self.record_path = self.dist_info_path + '/RECORD'
    self.data_path = self.base_path + '.data'

    self.data_paths = [
      'data',
      'headers',
      'scripts',
      'purelib',
      'platlib' ]

    super().__init__(
      outname = '-'.join( wheel_name_parts ) + '.whl',
      outdir = outdir,
      tmpdir = tmpdir,
      logger = logger,
      named_dirs = {
        'dist_info' : self.dist_info_path,
        **{ k : self.data_path + '/' + k for k in self.data_paths } } )

  #-----------------------------------------------------------------------------
  def finalize( self ):

    if self.record_hash:
      return self.record_hash

    self.check_top_level()

    self.write(
      dst = self.metadata_path,
      data = self.pkg_info.encode_pkg_info() )

    if self.pkg_info.license_file:
      self.write(
        dst = self.dist_info_path + '/' + self.pkg_info.license_file,
        data = self.pkg_info.license_file_content )

    self.write(
      dst = self.dist_info_path + '/' + 'top_level.txt',
      data = '\n'.join( self.top_level ) )

    self.write(
      dst = self.entry_points_path,
      data = self.pkg_info.encode_entry_points() )

    self.write(
      dst = self.wheel_path,
      data = self.encode_dist_info_wheel() )

    record_data, self.record_hash = self.encode_dist_info_record()

    self.write(
      dst = self.record_path,
      data = record_data,
      # NOTE: the record itself is not recorded in the record
      record = False )

    return self.record_hash

  #-----------------------------------------------------------------------------
  def check_top_level( self ):
    """Discover the package top_level from record entries
    """

    top_level = set()

    purelib = self.named_dirs['purelib'] + '/'
    purelib_len = len(purelib)

    platlib = self.named_dirs['platlib'] + '/'
    platlib_len = len(platlib)

    for file, hash, size in self.records:
      # check files added to purelib and platlib.
      if file.startswith(purelib):
        top_level.add( pkg_name(file[purelib_len:].split('/', 1)[0]) )

      elif file.startswith(platlib):

        self.purelib = False

        top_level.add( pkg_name(file[platlib_len:].split('/', 1)[0]) )

      elif not (
        file.startswith(self.dist_info_path)
        or file.startswith(self.data_path) ):

        # check any other files that aren't in .dist-info or .data
        top_level.add( pkg_name(file.split('/', 1)[0]) )

    self.top_level = [ dir for dir in top_level if dir ]

  #-----------------------------------------------------------------------------
  def encode_dist_info_wheel( self ):
    """Generate content for .dist_info/WHEEL

    Returns
    -------
    content : bytes
    """

    headers = [
      ( 'Wheel-Version', '1.0' ),
      ( 'Generator', self.gen_name ),
      ( 'Root-Is-Purelib', str(self.purelib).lower() ),
      *[ ( 'Tag', '-'.join( compat ) ) for compat in self.compat ],
      ( 'Build', self.build ) ]

    return email_encode_items( headers = headers )

  #-----------------------------------------------------------------------------
  def encode_dist_info_record( self ):
    """Generate content for .dist_info/RECORD

    Returns
    -------
    content : bytes
    hash : str
      sha256 hash of the record file data
    """

    record = io.StringIO()

    # the record file itself is listed in records, but the hash of the record
    # file cannot be included in the file.
    _records = self.records + [ ( self.record_path, '', '' ), ]

    for file, hash, size in _records:
      record.write( f'{file}, sha256={hash}, {size}\n' )

    content = record.getvalue().encode('utf-8')

    hash, size = hash_sha256( content )

    return content, hash
