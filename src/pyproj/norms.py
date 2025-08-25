from __future__ import annotations
import os
from io import (
  IOBase,
  BytesIO)
import stat
import re
import pathlib
from copy import copy
from collections.abc import (
  Mapping,
  Sequence,
  Iterable )

from collections import namedtuple
import hashlib
from base64 import urlsafe_b64encode
from email.message import Message
from email.generator import BytesGenerator
from email.utils import parseaddr, formataddr
from urllib.parse import urlparse

from packaging.tags import sys_tags
from packaging.markers import Marker

from .validate import (
  ValidationError,
  valid,
  valid_type,
  valid_keys,
  valid_dict,
  valid_list,
  mapget,
  as_list)

#===============================================================================
def marker_evaluated(marker):
  if isinstance(marker, bool):
    return marker

  marker = Marker(marker)

  return marker.evaluate()

#===============================================================================
def scalar(val):
  if isinstance(val, str):
    return val

  if isinstance(val, Iterable) or isinstance(val, Mapping):
    raise ValidationError(f"Must be a scalar: {val}")

  return val

#===============================================================================
class scalar_list(valid_list):
  value_valid = valid(scalar)

#===============================================================================
def norm_bool(val):
  t = [True, 'true', 'True', 'yes', 'y', 'enable', 'enabled']
  f = [False, 'false', 'False', 'no', 'n', 'disable', 'disabled']

  if val not in t + f:
    raise ValidationError(
      f"Value could not be interpreted as boolean: {val}")

  val = True if val in t else False

  return val

#===============================================================================
def empty_str(val):
  val = str(val)

  if len(val):
    raise ValidationError(
      f"Must be empty string")

  return val

#===============================================================================
def nonempty_str(val):
  val = str(val)

  if len(val) == 0:
    raise ValidationError(
      f"Must be non-empty string: {val}")

  return val

#===============================================================================
class str_list(valid_list):
  value_valid = valid(str)

#===============================================================================
class nonempty_str_list(valid_list):
  value_valid = valid(nonempty_str)

#===============================================================================
def norm_data(data: str|bytes|IOBase) -> bytes:
  """Normalize data for writing into a distribution

  Parameters
  ----------
  data:
    Data to process

  Returns
  -------
  data:

    * If data is bytes, it will be returned un-modified.
    * If data is a str, it will be encoded as 'utf-8'.
    * If data is a stream, it will be read to EOF and apply one of the above.
  """

  if isinstance(data, IOBase):
    # read from a stream, assumes readable
    data = data.read()

  if isinstance(data, str):
    # encode text as utf-8
    data = data.encode('utf-8')

  return data

#===============================================================================
def norm_path( path: str|pathlib.PurePath, parent_ok: bool = False) -> str:
  """Normalizes a file path for writing into a distribution archive

  Note
  ----
  * Must be a valid path
  * Must be relative, and no reference to parent any directory (e.g. '..')
  * May not contain any white-space in path components
  * All slashes replaced with forward slashes
  """

  path = os.fspath(path)

  if re.search( r'\s+', path ):
    raise ValidationError(
      f"path segments should not contain whitespace: {path}")

  # NOTE: starting with assuming windows path leads to the same result wether or
  # not it actually was a windows path, replacing slashes etc as necessary.
  # This should handle whether a path was passed in already posix-like, even when
  # on Windows.
  wpath = pathlib.PureWindowsPath( path )
  path = wpath.as_posix()

  if not parent_ok and re.search(r'(\.\.)', path):
    raise ValidationError(
      f"path segments can not be relative to parent directories: {path}")

  for segment in path.split('/'):
    if segment != '..' and windows_invalid_filename.fullmatch(segment):
      raise ValidationError(
        f"Path segment '{segment}' invalid on Windows platform: {path}")

  ppath = pathlib.PurePosixPath( path )

  if wpath.is_absolute() or ppath.is_absolute():
    raise ValidationError(f"path must be relative: {path}")

  return path

#===============================================================================
def norm_path_to_os( path ):
  """Converts a normalized or OS path to be an OS path
  """

  path = str(path)

  # NOTE: starting with assuming windows path leads to the same result wether or
  # not it actually was a windows path, replacing slashes etc as necessary.
  # This should handle whether a path was passed in already posix like even when
  # on Windows.
  wpath = pathlib.PureWindowsPath(path)
  path = wpath.as_posix()

  return str(pathlib.PurePath(path))

#===============================================================================
def norm_mode( mode = None ):
  """Normalizes file permission mode for distribution archive

  Parameters
  ----------
  mode : None | int
    POSIX permission mode

  Returns
  -------
  int

  Note
  ----
  The returned mode is either ``0o644`` (rw-r--r--), or `0o755` (rwxr-xr-x)
  if ``mode & stat.S_IXUSR == True``

  Example
  -------

  .. code-block:: python

    from partis.pyproj import norm_mode

    print( norm_mode( 0o000 ) == 0o644 )
    print( norm_mode( 0o100 ) == 0o755 )

  """

  if mode is None:
    mode = 0

  mode = int(mode)

  if mode & stat.S_IXUSR:
    # if the mode is executable by the user,
    # set as executable also by group and others

    # rwxr-xr-x
    _mode = 0o755

  else:
    # set as writable by owner, and readable by all others
    # rw-r--r--
    _mode = 0o644

  return _mode

#===============================================================================
def norm_zip_external_attr(mode = None, islink: bool = False):
  """Converts the unix integer mode to zip external_attr

  The returned value follows the 4 byte format
  ``|mm|mm|xx|dx|``

  The file permission mode is masked and shifted to the two most
  significant bytes.
  If specified as a directory, the second bit is set.

  Parameters
  ----------
  mode : int
  islink: bool
    Set the link flag

  Returns
  -------
  external_attr : int
  """


  xattr = norm_mode( mode )

  # mask and shift to 3rd byte
  xattr &= 0xFFFF

  if islink:
    xattr |= stat.S_IFLNK

  xattr = xattr << 16

  # set directory flag after shift
  # MS-DOS directory flag 0x10 (various sources,
  # e.g. https://stackoverflow.com/questions/434641 )
  # NOTE: not sure why this is necessary, except maybe for adding an empty directory
  # if stat.S_ISDIR(mode):
  #   xattr |= 0x10

  return xattr

#===============================================================================
def b64_nopad(data: bytes) -> str:
  """Encodes hash as urlsafe base64 encoding with no trailing '=' (:pep:`427`)

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0427/#appendix
  """
  return urlsafe_b64encode( data ).decode("ascii").rstrip("=")

#===============================================================================
def hash_sha256(stream: BytesIO|bytes) -> tuple[str, int]:
  """Computes SHA-256 hash

  Parameters
  ----------
  stream:

  Returns
  -------
  urlsafe base64 encoded hash, and size (in bytes) of the hashed data

  See Also
  --------
  :func:`hashlib.sha256`
  """

  if isinstance( stream, bytes ):
    with BytesIO( stream ) as _stream:
      return hash_sha256( _stream )

  hasher = hashlib.sha256()
  size = 0
  bufsize = 2**15

  while True:
    _data = stream.read( bufsize )
    _size = len(_data)

    if _size == 0:
      break

    size += _size
    hasher.update( _data )

  digest = hasher.digest()

  digest_b64_nopad = b64_nopad( digest )

  return digest_b64_nopad, size

#===============================================================================
def email_encode_items(
  headers,
  payload = None ):
  """Encodes a list of headers and a payload

  Parameters
  ----------
  headers : List[ Tuple[str, str ] ]
  payload : str

  Returns
  -------
  bytes

  See Also
  --------
  :mod:`email.message`

  """

  msg = Message()

  for k, v in headers:
    msg[k] = v

  if payload is not None:
    msg.set_payload( payload )

  buffer = BytesIO()

  gen = BytesGenerator(
    buffer,
    mangle_from_ = False,
    maxheaderlen = 0 )

  gen.flatten( msg )

  # TODO: why does ``wheel`` replace newlines with only carriage returns?
  # bytes = buffer.getvalue().replace(b'\r\n', b'\r')
  bytes = buffer.getvalue()

  return bytes

#===============================================================================
class TimeEncode:
  digits = '0123456789abcdefghijklmnopqrstuvwxyz'

  def __init__(self,
    resolution = 60,
    rollover = 60*(int('9zzz',36) + 1),
    width = 4,
    base = 36 ):
    """Encode unix timestamp

    Parameters
    ----------
    resolution : int
      Number of seconds that are resolved.
      The default resolution is 1 minute
    rollover : int
      Number of seconds upper bound before wrapping.
      The number of distinct values is ``rollover // resolution``.
      The default rollover is 324 days
    width : int
      Minimal width of encoded number
    base : int
      Numeric base used to encode number
    """

    assert base <= len(self.digits)

    self.resolution = resolution
    self.rollover = rollover
    self.modulus = rollover // resolution
    self.width = width
    self.base = base

  #-----------------------------------------------------------------------------
  @property
  def max(self):
    return self.encode( self.resolution * (self.modulus-1) )

  #-----------------------------------------------------------------------------
  def encode(self, num):
    num = ( int(num) // self.resolution ) % self.modulus
    res = []
    base = self.base
    digits = self.digits

    while num:
      num, i = divmod(num, base)
      res.append(digits[i])

    ts = ''.join(reversed(res))

    return f'{ts:0>{self.width}}'

#===============================================================================
# File/directory names that are invalid on windows
windows_invalid_filename = '|'.join([
  # filename ending with a period
  r'(.+\.)',
  # any characters in the range [0-31], or special characters <, >, :, \, ", ?, *
  r'((?=.*[\x00-\x1f<>:\"?*]).+)',
  # Any of these names, or followed immediately by an extension;
  # for example, NUL.txt
  *[ rf'({name}(\.\w+)?)'
    for name in [
      'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6',
      'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6',
      'LPT7', 'LPT8', 'LPT9' ] ] ])

windows_invalid_filename = re.compile(
  rf"^({windows_invalid_filename})$",
  re.VERBOSE | re.IGNORECASE | re.UNICODE )
