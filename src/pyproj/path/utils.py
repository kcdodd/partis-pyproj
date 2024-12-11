from __future__ import annotations
import sys
from os import (
  mkdir as os_mkdir,
  curdir,
  pardir)
from pathlib import (
  Path,
  PurePath)

#===============================================================================
class PathError(ValueError):
  pass

#===============================================================================
if sys.version_info < (3, 10):
  def mkdir(
      path: Path,
      mode: int = 0o777,
      parents: bool = False,
      exist_ok: bool = False):
    """Backport of :meth:`Path.mkdir`, mishandled parents/exist_ok on windows
    """
    try:
      os_mkdir(path, mode)

    except FileNotFoundError:
      if not parents or path.parent == path:
        raise
      mkdir(path.parent, parents=True, exist_ok=True)
      mkdir(path, mode, parents=False, exist_ok=exist_ok)
    except OSError:
      # Cannot rely on checking for EEXIST, since the operating system
      # could give priority to other errors like EACCES or EROFS
      if not exist_ok or not path.is_dir():
        raise
else:
  def mkdir(
      path: Path,
      mode: int = 0o777,
      parents: bool = False,
      exist_ok: bool = False):

    path.mkdir(mode=mode, parents=True, exist_ok=True)

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
