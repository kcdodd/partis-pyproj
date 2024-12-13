from __future__ import annotations
import sys
from os import (
  mkdir as os_mkdir,
  curdir,
  pardir,
  fspath)
from pathlib import (
  Path,
  PurePath)

#===============================================================================
class PathError(ValueError):
  pass

#===============================================================================
def mkdir(
    path: Path,
    mode: int = 0o777,
    parents: bool = False,
    exist_ok: bool = False):
  r"""Backport of :meth:`Path.mkdir` mishandled exist_ok on windows
  """
  print(f"mkdir({path}, {mode=}, {parents=}, {exist_ok=})")
  # if exist_ok and path.exists():
  #   if not path.is_dir():
  #     raise PathError(f"Path not a directory: {path}")

  #   return

  try:
    path.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
  except Exception as e:
    print(f"{type(e)}, {e=}, {getattr(e, 'filename', None)}, {isinstance(e, FileExistsError)}, {isinstance(e, OSError)}")
    print(f">> {fspath(path)=}")
    print(f">> {path.parts=}")
    print(f">> {path.exists()=}")
    print(f">> {path.is_file()=}")
    print(f">> {path.is_dir()=}")
    print(f">> {path.is_symlink()=}")
    print(f">> {path._accessor.mkdir}")
    try:
      print(f">> {path.stat()=}")
    except FileNotFoundError:
      print(">> path.stat()=None")

    raise e


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
