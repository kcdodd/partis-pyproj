"""This file supports incremental building for editable installs

Must define:
"""
from __future__ import annotations
from pathlib import Path
from os import (
  stat as os_stat,
  getcwd,
  chdir,
  path as osp)
from subprocess import check_output, check_call
import sys
import os
import platform
import time
from importlib.util import spec_from_file_location
from importlib.machinery import PathFinder

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
MODULES: dict[str, str] = {}

#@template@

# flag to only check once
INSTALLED: bool = False
# environment variable used to enable incremental build
ENV_NAME: str = 'PYPROJ_INCREMENTAL'
TRACKED_FILE = WHL_ROOT.parent/'tracked.csv'

#===============================================================================
def incremental():
  global INSTALLED
  if INSTALLED:
    return

  INSTALLED = True

  pkgs = os.environ.get(ENV_NAME)
  finder = None

  if pkgs:
    pkgs = pkgs.split(':')

    if PKG_NAME in pkgs:
      pkgs.remove(PKG_NAME)
      pkgs = ':'.join(pkgs)
      os.environ[ENV_NAME] = pkgs
      finder = IncrementalFinder(incremental=True)

  if finder is None:
    finder = IncrementalFinder(incremental=False)

  sys.meta_path.insert(0, finder)

#===============================================================================
class IncrementalFinder(PathFinder):
  """Issues warning if watched module is imported without incremental build
  """
  #-----------------------------------------------------------------------------
  def __init__(self, incremental: bool):
    self.checked = False
    self.incremental = incremental

  #-----------------------------------------------------------------------------
  def find_spec(self, fullname, path, target=None):
    # print(f"find_spec({fullname=}, {path=})")

    if fullname not in MODULES:
      return None

    # print(f"find_spec({fullname=}, {path=})")

    if not self.checked:
      self.checked = True
      self.rebuild()

    return super().find_spec(fullname, path, target)
    # location = osp.join(WHL_ROOT, location)
    # # print(f"find_spec({fullname=}, {path=})")
    # print(f">> {location}")
    # return spec_from_file_location(fullname, location)

  #-----------------------------------------------------------------------------
  def rebuild(self):
    changed, files_diff, commit, tracked_files = check_tracked()

    if not changed:
      return

    if not self.incremental:
      print(
        f"Editable package '{PKG_NAME}' source has changes ({len(files_diff)} files).",
        f"Add name to {ENV_NAME} for incremental builds.",
        file = sys.stderr)

      return

    # print(f"{fullname=}, {changed=}")
    # print('watched_diff:\n  '+'\n  '.join([str(v) for v in watched_diff]))

    # TODO: check hash here, but cannot import pyproj here
    # if pyproj.pptoml_checksum != PPTOML_CHECKSUM:

    host = platform.node()
    pid = os.getpid()
    mtime = 10*int(time.time())

    editable_root = WHL_ROOT.parent
    lockfile = editable_root/'incremental.lock'
    lockfile_tmp = editable_root/f'incremental.lock.{host}.{pid:d}.{mtime}'
    revfile = editable_root/'incremental.rev'

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

    print('\n'.join([
      f"Editable package '{PKG_NAME}' triggered incremental build:",
      f"  build: {_revision}",
      f"  machine: {_host}:{_pid}",
      f"  cached: {editable_root}",
      f"  source: '{SRC_ROOT}'",
      f"  changed ({len(files_diff)} files): " + ', '.join(f"'{v}'" for v in files_diff[:5])]),
      file = sys.stderr)

    if (_host, _pid, _mtime) == (host, pid, mtime):
      # this process obtained lock
      try:
        venv_dir = editable_root/'build_venv'
        venv_py = str(venv_dir/'bin'/'python')

        check_call([
          venv_py, '-m', 'partis.pyproj.cli', 'build',
          '--incremental',
          str(SRC_ROOT)])

        # update revision once completed
        revfile.write_text(str(_revision))
        update_tracked(commit, tracked_files)

      finally:
        lockfile.unlink()

    else:
      print(
        f"Editable '{PKG_NAME}' incremental build {_revision}:",
        f"Waiting on {_host}:{_pid} to finish",
        file = sys.stderr)

      # wait for running build
      while revision < _revision:
        time.sleep(1)

        if revfile.exists():
          revision = int(revfile.read_text())
        else:
          revision = 0

  #-----------------------------------------------------------------------------
  def invalidate_caches(self):
    super().invalidate_caches()


#===============================================================================
def check_tracked() -> tuple[bool, list[str], str, list[tuple[int,int,str]]]:
  """Check for changes to tracked files, returning lists of changed files and
  next tracked files
  """

  if not WHL_ROOT.is_dir():
    raise FileNotFoundError(
      f"Editable '{PKG_NAME}' staging directory not found: {WHL_ROOT}")

  if not SRC_ROOT.is_dir():
    raise FileNotFoundError(
      f"Editable '{PKG_NAME}' source directory not found: {SRC_ROOT}")

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
  # print('\n'.join([str(v) for v in tracked_diff]))
  files_diff = sorted(set([v[-1] for v in tracked_diff]))
  # ignore changes to pure-python files
  files_diff = [file for file in files_diff if not file.endswith('.py')]

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
def file_size_mtime(file: str) -> tuple[int,int,str]:
  """Gets mtime and size of file, or zero if file does not exist
  """
  try:
    st = os_stat(file)
    return int(st.st_mtime), st.st_size, file
  except FileNotFoundError:
    ...

  return 0, 0, file

#===============================================================================
def git_tracked_mtime(root: Path|None = None) -> tuple[str, list[tuple[int,int,str]]]:
  if root is None:
    return _git_tracked_mtime()

  cwd = getcwd()

  try:
    chdir(root)
    return _git_tracked_mtime()
  finally:
    chdir(cwd)

#===============================================================================
def _git_tracked_mtime() -> tuple[str, list[tuple[int,int,str]]]:

  commit = check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()
  # get listing of files to poll (tracked and non-ignored untracked files)
  files = check_output(['git', 'ls-files', '--exclude-standard', '-c', '-o']).decode('utf-8').splitlines()

  return commit, list(map(file_size_mtime, files))
