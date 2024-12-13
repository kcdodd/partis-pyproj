from __future__ import annotations
import sys
from os import (
  curdir,
  pardir,
  fspath)
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
