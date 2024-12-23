"""This is a template file

Must define:
"""
from __future__ import annotations
from pathlib import Path
from logging import getLogger
from subprocess import check_output
import sys
import os
import warnings
import platform
import time
import json
from importlib.machinery import PathFinder
from partis.pyproj.path import git_tracked_mtime

# name of editable package
PKG_NAME: str = ''
# package root source directory being edited
SRC_ROOT: Path = Path("")
# fake wheel directory prepared by `build_editable`
WHL_ROOT: Path = Path("")
# path to original backend generator
GEN_ROOT: Path = Path("")
# SHA base64 encoded checksum of 'pyproject.toml'
PPTOML_CHECKSUM: tuple[str, int] = ('', 0)
# config_settings originally given
CONFIG_SETTINGS: dict = {}
# list of module names to watch for
WATCHED: set[str] = set()

#@template@

# flag to only check once
INSTALLED: bool = False
# environment variable used to enable incremental build
ENV_NAME: str = 'PYPROJ_INCREMENTAL'
TRACKED_FILE = WHL_ROOT/'tracked.csv'

#===============================================================================
def incremental():
  global INSTALLED
  if INSTALLED:
    return

  INSTALLED = True

  if not (WHL_ROOT.exists() and WHL_ROOT.is_dir()):
    warnings.warn(
      f"Editable '{PKG_NAME}' staging directory not found: {WHL_ROOT}")

    return

  if not (SRC_ROOT.exists() and SRC_ROOT.is_dir()):
    warnings.warn(
      f"Editable '{PKG_NAME}' source directory not found: {SRC_ROOT}")

    return

  pkgs = os.environ.get(ENV_NAME)
  finder = None

  if pkgs:
    pkgs = pkgs.split(':')

    if PKG_NAME in pkgs:
      pkgs.remove(PKG_NAME)
      pkgs = ':'.join(pkgs)
      os.environ[ENV_NAME] = pkgs
      finder = IncrementalFinder()

  if finder is None:
    finder = NoIncrementalFinder()

  sys.meta_path.insert(0, finder)

#===============================================================================
def check_tracked() -> tuple[bool, list[str], str, list[tuple[int,int,str]]]:
  """Check for changes to tracked files, returning lists of changed files and
  next tracked files
  """

  tracked = TRACKED_FILE.read_text().splitlines()
  commit = tracked[0]
  tracked_files = []

  for line in tracked[1:]:
    parts = [v.strip() for v in line.split(',', maxsplit=2)]

    if len(parts) != 3:
      raise ValueError(f"Tracked file appears corrupt: {line}")

    mtime, size, file  = parts
    stat = (int(mtime), int(size), file)
    tracked_files.append(stat)

  _commit, _tracked_files = git_tracked_mtime(SRC_ROOT)

  tracked_diff = list(set(tracked_files)^set(_tracked_files))
  files_diff = [v[-1] for v in tracked_diff]
  changed = not (commit == _commit and not files_diff)

  return changed, files_diff, _commit, _tracked_files

#===============================================================================
def update_tracked(commit: str, tracked_files: list[tuple[int,int,str]]):
  """Write list of tracked files back to file
  """
  TRACKED_FILE.write_text('\n'.join([
    commit,
    *[f"{mtime}, {size}, {file}"
      for mtime, size, file,  in tracked_files]]))

#===============================================================================
def build_incremental():
  logger = getLogger(__name__)

  try:
    import partis.pyproj as gen_mod
    from partis.pyproj.backend import backend_init

    _gen_root = Path(gen_mod.__file__).parent

    if _gen_root != GEN_ROOT:
      warnings.warn(
        f"Editable '{PKG_NAME}' generator location has changed, incremental build may not work correctly: '{GEN_ROOT}' -> '{_gen_root}'")

    pyproj = backend_init(
      root = SRC_ROOT,
      config_settings = CONFIG_SETTINGS,
      editable = True,
      logger = logger,
      init_logging = False)

    if pyproj.pptoml_checksum != PPTOML_CHECKSUM:
      logger.warning(
        f"Editable '{PKG_NAME}' source pyproject.toml has changed, incremental build may not work correctly.")

    pyproj.dist_binary_prep(incremental = True)

  except Exception as e:
    warnings.warn(f"Editable '{PKG_NAME}' check failed, incremental build may not work correctly.")

#===============================================================================
class NoIncrementalFinder(PathFinder):
  """Issues warning if watched module is imported without incremental build
  """
  #-----------------------------------------------------------------------------
  def __init__(self):
    self.checked = False

  #-----------------------------------------------------------------------------
  def find_spec(self, fullname, path, target=None):
    if path is not None or self.checked:
      return None

    basename = fullname.split('.')[0]
    watched = basename in WATCHED

    if not watched:
      return None

    self.checked = True
    changed, files_diff, commit, tracked_files = check_tracked()

    if changed:
      warnings.warn(
        f"Editable installed package '{PKG_NAME}' source has changes ({len(files_diff)} files)."
        + f" Add name to {ENV_NAME} for automatic incremental builds.")

#===============================================================================
class IncrementalFinder(NoIncrementalFinder):
  #-----------------------------------------------------------------------------
  def find_spec(self, fullname, path, target=None):
    if path is not None or self.checked:
      return None

    basename = fullname.split('.')[0]
    watched = basename in WATCHED

    if not watched:
      return None

    self.checked = True
    changed, files_diff, commit, tracked_files = check_tracked()

    # print('watched_diff:\n  '+'\n  '.join([str(v) for v in watched_diff]))

    if changed:
      host = platform.node()
      pid = os.getpid()
      mtime = 10*int(time.time())

      lockfile = WHL_ROOT/'incremental.lock'
      lockfile_tmp = WHL_ROOT/f'incremental.lock.{host}.{pid:d}.{mtime}'
      revfile = WHL_ROOT/'incremental.rev'

      if revfile.exists():
        revision = int(revfile.read_text())
      else:
        revision = 0

      key = f"{host},{pid:d},{mtime:d},{revision+1:d}"

      if not lockfile.exists():
        lockfile_tmp.write_text(key)
        os.replace(lockfile_tmp, lockfile)

      _host, _pid, _mtime, _revision = lockfile.read_text().split(',')

      _pid = int(_pid)
      _mtime = int(_mtime)
      _revision = int(_revision)

      if (_host, _pid, _mtime) == (host, pid, mtime):
        # this process obtained lock
        try:
          print(
            "-------------------------------------------------------------------"
            + f"Editable '{PKG_NAME}' incremental build {_revision}:"
            + f"  changed ({len(files_diff)} files): " + ', '.join(f"'{v}'" for v in files_diff[:5])
            + f" repository: '{SRC_ROOT}'")

          # self.build_incremental(logger)

          # update revision once completed
          revfile.write_text(str(_revision))
          update_tracked(commit, tracked_files)
          print("-------------------------------------------------------------------")

        finally:
          lockfile.unlink()

      else:
        warnings.warn(f"Editable '{PKG_NAME}' incremental revision {_revision}: waiting on {_host}:{_pid} to finish")

        # wait for running build
        while revision < _revision:
          time.sleep(1)

          if revfile.exists():
            revision = int(revfile.read_text())
          else:
            revision = 0

    return super().find_spec(fullname, path, target)

  #-----------------------------------------------------------------------------
  def invalidate_caches(self):
    super().invalidate_caches()

