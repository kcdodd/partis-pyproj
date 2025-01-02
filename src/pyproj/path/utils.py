from __future__ import annotations
from subprocess import check_output
from os import (
  curdir,
  pardir,
  fspath,
  stat as os_stat,
  getcwd,
  chdir)
from os.path import (
  realpath)
from pathlib import (
  Path,
  PurePath)

#===============================================================================
class PathError(ValueError):
  pass

#===============================================================================
def resolve(path: Path):
  r"""Backport of latest Path.resolve behavior
  """
  return type(path)(realpath(fspath(path)))

#===============================================================================
def _concretize(comps: list[str]) -> list[str]|None:
  r"""Mostly equivalent to :func:`os.path.normpath`, except for the cases where
  a concrete path is not possible or would be truncated.

  For example, the path `a/../b` can be normalized to the concrete path `b`,
  but `a/../../b` depends the name of a's parent directory.
  """

  new_comps = []

  for comp in comps:
    if not comp or comp == curdir:
      continue

    if comp == pardir:
      if not new_comps:
        # concrete path not possible
        return None

      new_comps.pop()
    else:
      new_comps.append(comp)

  return new_comps

#===============================================================================
def _subdir(_start: list[str], _path: list[str]) -> list[str]|None:
  r"""Concrete path relative to start, or `None` if path is not a sub-directory
  """

  if (_start := _concretize(_start)) is None:
    return None

  if (_path := _concretize(_path)) is None:
    return None

  n = len(_start)

  if len(_path) < n or _path[:n] != _start:
    return None

  return _path[n:]

#===============================================================================
def subdir(start: PurePath, path: PurePath, check: bool = True) -> PurePath|None:
  """Relative path, restricted to sub-directories.

  Parameters
  ----------
  start:
    Starting directory.
  path:
    Directory to compute relative path to, *must* be a sub-directory of `start`.
  check:
    If True, raises exception if not a subdirectory. Otherwise returns None.

  Returns
  -------
  rpath:
    Relative path from `start` to `path`.
  """

  _rpath = _subdir(start.parts, path.parts)

  if _rpath is None:
    if check:
      raise PathError(f"Not a subdirectory of {start}: {path}")

    return None

  return type(path)(*_rpath)

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
