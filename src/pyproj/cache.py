from __future__ import annotations
import hashlib
import os
import tempfile
from pathlib import Path

CACHE_DIR: Path|None = None

#===============================================================================
def cache_dir() -> Path:
  if CACHE_DIR is not None:
    return CACHE_DIR

  # NOTE: an environment variable, and not only the module value, since the cache
  # must also be re-directed for any 'partis-pyproj' sub-process
  if _cache_dir := os.environ.get('PARTIS_PYPROJ_CACHE_DIR'):
    return Path(_cache_dir)

  try:
    # prefer user home directory to avoid clashing in global "tmp" directory
    return Path.home()/'.cache'/'partis-pyproj'
  except RuntimeError:
    ...

  # use global temporary directory, suffixed by username to try to avoid conficts
  # between users
  import getpass
  username = getpass.getuser()
  tmp_dir = tempfile.gettempdir()
  return Path(tmp_dir)/f'.cache-partis-pyproj-{username}'

#===============================================================================
def cache_dirname(path: str|Path) -> str:
  """Name a single cache directory after a filesystem path

  Only the final component of the path is kept, prefixed by a short hash of the
  whole path, since that component alone is not unique: two source trees may end
  in the same directory name.

  Parameters
  ----------
  path:
    Absolute path the cache entry corresponds to. Must already be resolved for
    the name to be stable, and its final component must already be a valid, short
    directory name. A build environment is created *within* a cache entry, and
    the longest path below the environment root measured for a meson build
    environment is ~100 characters, so a long name leaves the environment
    unusable on Windows, e.g. "ImportError: DLL load failed while importing
    tomli: The filename or extension is too long".
  """
  path = Path(path)

  # hash of path used to prevent collision after only the final component is kept
  h = hashlib.sha256()
  h.update(str(path).encode('utf-8'))
  # keep only 4 bytes (8 hex characters) worth of the hash
  short = h.digest()[:4].hex()

  name = path.name

  return f"{short}-{name}"
