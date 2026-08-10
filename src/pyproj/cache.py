from __future__ import annotations
import hashlib
import os
import re
import tempfile
from pathlib import Path

CACHE_DIR: Path|None = None

_dirname_subs = re.compile(r'[^a-z0-9\.\-\_]+', re.IGNORECASE)

# Limits the sanitized path, which is otherwise unbounded.
# A build environment is created *within* a cache entry, and the longest path
# below the environment root measured for a meson build environment is ~100
# characters, so the entry name must stay short enough that the total remains
# under the Windows MAX_PATH limit of 260 characters. Otherwise the environment
# is created but unusable, e.g. "ImportError: DLL load failed while importing
# tomli: The filename or extension is too long".
_DIRNAME_MAX = 32

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
  """Sanitize a filesystem path for use as a single cache directory name

  The name is prefixed by a short hash of the un-sanitized path, since the
  substitution is not injective (e.g. '/a/b' and '/a_b' both sanitize to 'a_b'),
  and the sanitized path is truncated from the left, keeping the trailing
  segments that identify what the entry is for.

  Parameters
  ----------
  path:
    Absolute path the cache entry corresponds to. Must already be resolved for
    the name to be stable.
  """
  path = str(path)

  # hash of path used to prevent collision after path is sanitized
  h = hashlib.sha256()
  h.update(path.encode('utf-8'))
  # keep only 4 bytes (8 hex characters) worth of the hash
  short = h.digest()[:4].hex()

  name = _dirname_subs.sub('_', path).strip('_')

  return f"{short}-{name[-_DIRNAME_MAX:].lstrip('_')}"
