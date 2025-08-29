from __future__ import annotations
import os
import io
import re
import csv
import shutil
import json
from subprocess import check_output
from pathlib import (
  Path,
  PurePosixPath)
from ..norms import (
  norm_path,
  norm_data,
  hash_sha256,
  email_encode_items)
from ..pep import (
  norm_dist_build,
  norm_dist_compat,
  compress_dist_compat,
  norm_dist_filename,
  CompatibilityTags)
from ..pkginfo import PkgInfo
from .dist_zip import dist_zip
from ..path import (
  subdir,
  PathError,
  git_tracked_mtime)

#===============================================================================
def pkg_name(dir):
  if dir.endswith('.py'):
    return dir[:-3]

  return dir

#===============================================================================
def module_name_from_path(path):
  if path.name.startswitch('__init__'):
    parts = path.parent.parts

  else:
    parts = path.parts
    name = parts[-1]
    name = name.partition('-')


#===============================================================================
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

    # Mark as purelib only if no ABI or platform tags are specified. While ABI
    # is not technically platform specific, it does indicate that there are compiled
    # extensions that require ABI compatibility until a use-case presents itself
    # where ABI does not imply platlib.
    self.purelib = all(
      abi_tag == 'none' and plat_tag == 'any'
      for py_tag, abi_tag, plat_tag in compat)

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

    self.base_path = PurePosixPath('-'.join( wheel_name_parts[:2] ))
    self.base_tag = '-'.join( wheel_name_parts[-3:] )

    self.dist_info_path = PurePosixPath(str(self.base_path) + '.dist-info')
    self.data_path = PurePosixPath(str(self.base_path) + '.data')
    self.metadata_path = self.dist_info_path.joinpath('METADATA')
    self.entry_points_path = self.dist_info_path.joinpath('entry_points.txt')
    self.wheel_path = self.dist_info_path.joinpath('WHEEL')
    self.record_path = self.dist_info_path.joinpath('RECORD')

    self.data_paths = [
      'data',
      'headers',
      'scripts']

    # NOTE: Previously ".data/purelib" and ".data/platlib" were used exclusively
    # according to PEP 427.
    # But according to packaging guildlines, in practice all package files
    # that will go into site-packages should be located at the root of the
    # distribution, regardless of their purelib/platlib status, and the
    # distribution marked `Root-Is-Purelib: [true|false]` as a whole.
    # Supporting ".data/purelib" and ".data/platlib", in addition to root pure/plat
    # just leads to confusion as to how to where the files should go since they
    # would end up in the same place in virtually all circumstances.
    # Basically, if *anything* goes into 'platlib' then the whole distribution should
    # just be platlib.

    self.pkg_paths = [
      'purelib',
      'platlib' ]

    super().__init__(
      outname = '-'.join( wheel_name_parts ) + '.whl',
      outdir = outdir,
      tmpdir = tmpdir,
      logger = logger,
      named_dirs = {
        'dist_info' : self.dist_info_path,
        **{k: PurePosixPath('.') for k in self.pkg_paths},
        **{k : self.data_path.joinpath(k) for k in self.data_paths } } )

  #-----------------------------------------------------------------------------
  def finalize(self, metadata_directory: str|None = None):

    if self.record_hash:
      return self.record_hash

    self.check_top_level()

    self.write(
      dst = self.metadata_path,
      data = self.pkg_info.encode_pkg_info() )

    if self.pkg_info.license_file:
      self.write(
        dst = self.dist_info_path.joinpath(self.pkg_info.license_file),
        data = self.pkg_info.license_file_content )

    self.write(
      dst = self.dist_info_path.joinpath('top_level.txt'),
      data = '\n'.join( self.top_level ) )

    self.write(
      dst = self.entry_points_path,
      data = self.pkg_info.encode_entry_points() )

    self.write(
      dst = self.wheel_path,
      data = self.encode_dist_info_wheel() )

    record_data, self.record_hash = self.encode_dist_info_record()

    if metadata_directory is not None:
      print(f"{metadata_directory=}")
      # pep-517: MUST be identical to the directory created by
      # prepare_metadata_for_build_wheel, including any unrecognized files it
      # created.

      # check for unrecognized files and copy into dist_info
      dist_info = self.named_dirs['dist_info']

      for file in Path(metadata_directory).iterdir():
        if file.name == 'RECORD':
          continue

        _file = dist_info/file.relative_to(metadata_directory).as_posix()

        if self.exists(_file):
          continue

        self.copyfile(file, _file)


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

    dist_info = self.dist_info_path.name
    data = self.data_path.name

    for file, (hash, size) in self.records.items():
      # check files added to purelib or platlib.
      if (top := file.parts[0]) not in (dist_info, data):
        top_level.add(pkg_name(top))

    self.top_level = [ top for top in top_level if top ]

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
    record_csv = csv.writer(record)

    # the record file itself is listed in records, but the hash of the record
    # file cannot be included in the file.
    _records = {**self.records, self.record_path: ('', '')}

    for file, (hash, size) in _records.items():
      hash = f'sha256={hash}' if hash else ''
      record_csv.writerow([os.fspath(file), hash, size])

    content = record.getvalue().encode('utf-8')

    hash, size = hash_sha256(content)

    return content, hash


#===============================================================================
class dist_binary_editable( dist_binary_wheel ):
  """Builds a file-system based distribution as part of an editable installs

  Parameters
  ----------
  root:
    Editable project root with pyproject.toml
  incremental:
    Setup editable install for incremental rebuilds (re-runs targets upon changes)
  pptoml_checksum:
  whl_root:
    fake wheel directory prepared by `build_editable`
  """
  root: Path
  pptoml_checksum: tuple[str, int]
  whl_root: Path

  #-----------------------------------------------------------------------------
  def __init__( self, *,
    root: Path,
    incremental: bool,
    pptoml_checksum: tuple[str, int],
    whl_root: Path,
    pkg_info: PkgInfo,
    build: str = '',
    compat: list[tuple[str,str,str]|CompatibilityTags]|None = None,
    outdir = None,
    tmpdir = None,
    logger = None,
    gen_name = None ):

    super().__init__(
      pkg_info = pkg_info,
      build = build,
      compat = compat,
      outdir = outdir,
      tmpdir = tmpdir,
      logger = logger,
      gen_name = gen_name)

    self.root = root
    self.incremental = incremental
    self.pptoml_checksum = pptoml_checksum
    self.whl_root = whl_root

    if incremental and not (root/'.git').exists():
      raise NotImplementedError(
        f"Incremental editable installs are only supported from a source repository: {self.root}")

  #-----------------------------------------------------------------------------
  def finalize(self, metadata_directory: str|None = None): # pragma: no cover
    dist = dist_binary_wheel(
      pkg_info = self.pkg_info,
      build = self.build,
      compat = self.compat,
      outdir = self.outdir,
      tmpdir = self.tmpdir,
      logger = self.logger,
      gen_name = self.gen_name)

    root = self.root
    whl_root = self.whl_root
    # path to "generator" (partis.pyproj)
    gen_root = Path(__file__).parent.parent
    purelib = dist.named_dirs['purelib']
    self.check_top_level()

    pkg_name = norm_dist_filename(self.pkg_info.name_normed)
    pth_file = pkg_name+'.pth'


    dist_info = self.dist_info_path.name
    data = self.data_path.name

    paths = set()

    for file, (hash, size) in self.records.items():
      # check directories added to purelib/platlib.
      if file.parts[0] not in (dist_info, data):
        if len(file.parts) == 1 or file.name.startswith("__init__."):
          paths.add(file)
        else:
          paths.add(file.parent)

    modules = {}

    for path in paths:
      if path.name.startswith("__init__."):
        fullname = '.'.join(path.parent.parts)
      else:
        fullname = '.'.join(path.parts).removesuffix('.py')

      modules[fullname] = str(path)


    if self.incremental:
      editable_root = whl_root.parent
      commit, tracked_files = git_tracked_mtime()
      tracked_file = editable_root/'tracked.csv'
      tracked_file.write_text('\n'.join([
        commit,
        *[f"{mtime}, {size}, {file}"
          for mtime, size, file  in tracked_files]]))

      check_module_name = pkg_name + '_incremental'
      check_file_out = check_module_name+'.py'
      check_file_in = gen_root/'_incremental.py'
      check_content = check_file_in.read_text()

      header, _, footer = check_content.partition("#@template@")
      _modules = ',\n'.join(f"  {k!r}: {v!r}" for k,v in modules.items())

      check_content = '\n'.join([
        header,
        f"PKG_NAME = '{self.pkg_info.name_normed}'",
        f"SRC_ROOT = Path('{self.root}')",
        f"WHL_ROOT = Path('{whl_root}')",
        f"GEN_ROOT = Path('{gen_root}')",
        f"PPTOML_CHECKSUM = {self.pptoml_checksum!r}",
        f"MODULES = {{\n{_modules}}}",
        footer])

      pth_content = '\n'.join([
        str(whl_root),
        f"import {check_module_name}; {check_module_name}.incremental()"])


      with dist:
        dist.write(purelib/pth_file, pth_content.encode('utf-8'))
        dist.write(purelib/check_file_out, check_content.encode('utf-8'))
        record_hash = dist.finalize(metadata_directory)

    else:
      pth_content = str(whl_root)

      with dist:
        dist.write(purelib/pth_file, pth_content.encode('utf-8'))
        record_hash = dist.finalize(metadata_directory)

    return record_hash

  #-----------------------------------------------------------------------------
  def create_distfile( self ):
    # need to create a filesystem equivalent for the wheel
    self.whl_root.mkdir(0o700, parents=True, exist_ok=True)

  #-----------------------------------------------------------------------------
  def close_distfile( self ):
    pass

  #-----------------------------------------------------------------------------
  def copy_distfile( self ):
    # TODO: could make a directory somewhere else, and then symlink it to its
    # final location (that will be added to search paths) during copy_distfile

    pass

  #-----------------------------------------------------------------------------
  def remove_distfile( self ):
    pass

  # #-----------------------------------------------------------------------------
  # def makedirs( self,
  #   dst: PurePosixPath,
  #   mode: int|None = None,
  #   exist_ok: bool = False,
  #   record: bool = True ):

  #   _dir = self.whl_root
  #   _dst = _dir/Path(norm_path(os.fspath(dst)))

  #   if _dst.exists():
  #     if not exist_ok:
  #       raise PathError(f"Build file already has entry: {_dst}")

  #   else:
  #     _dst.mkdir(parents=True)

  #-----------------------------------------------------------------------------
  def copyfile( self,
    src: Path,
    dst: PurePosixPath,
    mode: int|None = None,
    exist_ok: bool = False,
    record: bool = True ):

    src = Path(src)
    src = src.resolve()

    _dst = self.whl_root/Path(norm_path(os.fspath(dst)))

    if not src.exists():
      raise PathError(f"Source file not found: {src}")

    if not exist_ok and self.exists( dst ):
      raise PathError(f"Build file already has entry: {dst}")

    if not _dst.parent.exists():
      _dst.parent.mkdir(parents=True)

    self.logger.debug(f'copyfile {src}')

    if mode is None:
      mode = src.stat().st_mode

    # TODO: set mode on link?
    _dst.symlink_to(src)

    if record:
      self.record(
        dst = dst,
        data = str(_dst).encode('utf-8'))

    return dst

  #-----------------------------------------------------------------------------
  def write( self,
    dst,
    data,
    mode = None,
    record = True ):

    self.assert_open()

    dst = norm_path(os.fspath(dst))
    _dir = self.whl_root
    _dst = _dir/Path(norm_path(os.fspath(dst)))

    if not _dst.parent.exists():
      _dst.parent.mkdir(parents=True)

    data = norm_data( data )

    # TODO: set mode on file?
    _dst.write_bytes(data)

    if record:
      self.record(
        dst = dst,
        data = data )

  #-----------------------------------------------------------------------------
  def exists( self,
    dst ):

    self.assert_open()

    _dir = self.whl_root
    _dst = _dir/Path(norm_path(os.fspath(dst)))
    return _dst.exists()

