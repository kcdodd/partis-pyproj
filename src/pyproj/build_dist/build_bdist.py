import os
import os.path as osp
import io
import warnings
import stat

import tempfile
import shutil

from ..norms import (
  norm_dist_name,
  norm_dist_build,
  norm_dist_compat,
  compress_dist_compat,
  norm_wheel_name,
  norm_path,
  norm_data,
  hash_sha256,
  email_encode_items )

from ..pkginfo import PkgInfo

from .build_zip import build_zip

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_bdist_wheel( build_zip ):
  """Build a binary distribution ``*.whl`` wheel file

  Parameters
  ----------
  pkg_info : :class:`PkgInfo <partis.pyproj.pkginfo.PkgInfo>`
  build : str
    Build tag. Must start with a digit, or be an empty string.
  compat : List[ Tuple[str,str,str] ]
    List of build compatability tuples of the form ( py_tag, abi_tag, plat_tag ).
    e.g. ( 'py3', 'abi3', 'linux_x86_64' )
  purelib : bool
    If ``True``, the installer will assume that all modules are pure python.
  top_level : List[ str ]
    Names of top-level packages.
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
        build_bdist_wheel )

      pkg_info = PkgInfo(
        project = dict(
          name = 'my-package',
          version = '1.0' ) )


      with build_bdist_wheel(
        pkg_info = pkg_info,
        top_level = [ 'my_package' ],
        outdir = out_dir ) as bdist:

        bdist.copytree(
          src = pkg_dir,
          dst = 'my_package' )

      print( bdist.outname )
      print( os.path.relpath( bdist.outpath, tmpdir ) )

  .. testoutput::

    my_package-1.0-py3-none-any.whl
    build/my_package-1.0-py3-none-any.whl


  See Also
  --------
  * https://www.python.org/dev/peps/pep-0427
  * https://www.python.org/dev/peps/pep-0660

  """
  #-----------------------------------------------------------------------------
  def __init__( self, *,
    pkg_info,
    build = '',
    compat = [ ( 'py3', 'none', 'any' ), ],
    purelib = True,
    top_level = None,
    outdir = None,
    tmpdir = None,
    logger = None,
    gen_name = 'build_bdist_wheel', ):

    if not isinstance( pkg_info, PkgInfo ):
      raise ValueError(f"pkg_info must be instance of PkgInfo: {pkg_info}")

    self.pkg_info = pkg_info

    if len(self.pkg_info.dynamic) > 0:
      raise ValueError(
        f'dynamic package meta-data must be resolved before building dist: {self.pkg_info.dynamic}')

    if top_level is None:
      top_level = list()

    self.top_level = [ norm_dist_name(d) for d in top_level ]

    self.build = norm_dist_build( build )

    self.compat = [
      norm_dist_compat( py_tag, abi_tag, plat_tag )
      for py_tag, abi_tag, plat_tag in compat ]

    self.purelib = bool(purelib)
    self.gen_name = str(gen_name)

    wheel_name_parts = [
      self.pkg_info.name_normed,
      self.pkg_info.version,
      self.build,
      *compress_dist_compat( self.compat ) ]

    wheel_name_parts = [
      norm_wheel_name(p)
      for p in wheel_name_parts
      if p != '' ]

    self.base_path = '-'.join( wheel_name_parts[:2] )
    self.base_tag = '-'.join( wheel_name_parts[-3:] )

    self.dist_info_path = self.base_path + '.dist-info'
    self.data_path = self.base_path + '.data'
    self.metadata_path = self.dist_info_path + '/METADATA'
    self.entry_points_path = self.dist_info_path + '/entry_points.txt'
    self.wheel_path = self.dist_info_path + '/WHEEL'
    self.record_path = self.dist_info_path + '/RECORD'

    super().__init__(
      outname = '-'.join( wheel_name_parts ) + '.whl',
      outdir = outdir,
      tmpdir = tmpdir,
      logger = logger )

  #-----------------------------------------------------------------------------
  def finalize( self ):

    if self.record_hash:
      return self.record_hash

    self.write(
      dst = self.metadata_path,
      data = self.pkg_info.encode_pkg_info() )

    if self.pkg_info.license_file:
      self.write(
        dst = self.dist_info_path + '/' + self.pkg_info.license_file,
        data = self.pkg_info.license_file_content )

    if len(self.top_level) > 0:
      self.write(
        dst = self.dist_info_path + '/' + 'top_level.txt',
        data = '\n'.join(self.top_level) )

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
