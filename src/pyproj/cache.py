from __future__ import annotations
import tempfile
from pathlib import Path

CACHE_DIR: Path|None = None

#===============================================================================
def cache_dir() -> Path:
  if CACHE_DIR is not None:
    return CACHE_DIR

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