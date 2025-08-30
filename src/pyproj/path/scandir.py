from __future__ import annotations
from pathlib import Path, PurePath
from typing import NamedTuple
import os
import stat
from os import (
  scandir as os_scandir,
  readlink as os_readlink,
  sep as os_sep)
from . import (
  tr_path,
  PathFilter)

#===============================================================================
class FileInfo(NamedTuple):
  mtime: int
  r"""Last modified time
  """
  size: int
  r"""Size of file in bytes
  """
  link: PurePath|None = None
  r"""If file is a symbolic link, this is the links target
  """

#===============================================================================
class DirInfo(NamedTuple):
  files: dict[str, FileInfo]
  r"""File names and info in this directory
  """
  dirs: dict[str, DirInfo]
  r"""Directory names and info in this directory
  """
  ignore: list[str]|None
  r"""Equivalent to a ".gitignore" present in this directory
  """
  errors: dict[str, str]
  r"""File or directory names that resulted in error messages in this directory
  """

  #-----------------------------------------------------------------------------
  def get(self, path: PurePath|list[str]) -> DirInfo|FileInfo:
    r"""Return the info for directory or file
    """

    if isinstance(path, list):
      path = PurePath(*path)
    else:
      path = PurePath(path)

    assert not path.is_absolute()
    parts = path.parts

    if not parts:
      return self

    cur = self

    for name in parts[:-1]:
      _cur = cur.dirs.get(name)

      if _cur is None:
        raise FileNotFoundError(f"No directory {path}")

      cur = _cur

    name = parts[-1]
    _cur = cur.dirs.get(name)

    if _cur is None:
      _cur = cur.files.get(name)

    if _cur is None:
      raise FileNotFoundError(f"No file or directory {path}")

    return _cur

  #-----------------------------------------------------------------------------
  def glob(self,
      include: PathFilter,
      exclude: PathFilter|tuple[PathFilter]|None = None,
      ignore: bool = False,
      dirpath: PurePath = PurePath()) -> list[tuple[PurePath, FileInfo]]:
    r"""Similar to performing glob on a directory with the same content, but does
    not use any filesystem access.

    Parameters
    ----------
    include:
      The equivalent of the glob pattern, filters for files to include
    exclude:
      If given, removes matches.
    ignore:
      If true, also excludes based on pre-existing `DirInfo.ignore` (.gitignore)
    dirpath:
      If given, serves as the path for the starting directory where `glob` was
      called, all matched paths will begin with this path.
    """

    if isinstance(exclude, PathFilter):
      exclude = (exclude,)
    elif exclude is None:
      exclude = ()
    else:
      exclude = tuple(exclude)

    return self._glob(dirpath, include, exclude, ignore)

  #-----------------------------------------------------------------------------
  def _glob(self,
      dirpath: PurePath,
      include: PathFilter|None,
      excludes: tuple[PathFilter],
      ignore: bool) -> list[tuple[PurePath, FileInfo]]:

    _dirpath = tr_path(dirpath)
    fnames = list(self.files.keys())
    dnames = list(self.dirs.keys())

    if include is None:
      included = set(fnames+dnames)
    else:
      included = include._filter(
        _dirpath,
        fnames = fnames,
        dnames = dnames)

    if ignore and self.ignore is not None:
      excludes = (PathFilter(self.ignore, start = dirpath),) + excludes

    excluded = set()

    for exclude in excludes:
      excluded = exclude._filter(
        _dirpath,
        fnames,
        dnames,
        excluded)

    included = included - excluded

    files = [
      (dirpath/name, info) for name, info in self.files.items()
      if name in included]

    for name, info in self.dirs.items():
      if name in included:
        # The directory matched the include pattern,
        # treat as though everything under the directory also matches
        files.extend(info._glob(dirpath/name, None, excludes, ignore))

      elif name not in excluded:
        # directory is still recursed if not ignored,
        # but individual items must still match the include pattern
        files.extend(info._glob(dirpath/name, include, excludes, ignore))

    return files

  #-----------------------------------------------------------------------------
  def __str__(self):
    args = ', '.join([
      f"files={set(self.files.keys())}",
      f"dirs={set(self.dirs.keys())}",
      f"ignore={self.ignore}",
      f"errors={set(self.errors.keys())}"])

    return f"{type(self).__name__}({args})"

#===============================================================================
def scandir_recursive(
    root: Path,
    follow_symlinks: bool = False,
    gitignore: bool = False) -> DirInfo:
  r"""Returns all file paths under given root directory

  Parameters
  ----------
  root:
    Starting point of directory recursion
  follow_symlinks:
    Whether or not to follow symlinks when recursing and collecting file info
  gitignore:
    If true, reads .gitignore files as they encountered and stores the patterns
    in DirInfo.ignore. These are *not* used during the scan, all files will
    still be returned.
  """
  files = {}
  dirs = {}
  errors = {}
  ignore = None
  entry: os.DirEntry

  try:
    with os_scandir(root) as entries:
      for entry in entries:
        path = entry.path

        try:
          s = entry.stat(follow_symlinks=follow_symlinks)

          if stat.S_ISLNK(s.st_mode):
            files[entry.name] = FileInfo(
              s.st_mtime,
              s.st_size,
              PurePath(os_readlink(path)))

          elif stat.S_ISDIR(s.st_mode):
            dirs[entry.name] = scandir_recursive(path, follow_symlinks, gitignore)

          else:
            files[entry.name] = FileInfo(
              s.st_mtime,
              s.st_size)

            if gitignore and entry.name == '.gitignore':
              with open(entry.path, 'r') as fp:
                ignore = [line.strip() for line in fp.read().splitlines()]

              ignore = [line for line in ignore if not line.startswith('#')]

        except OSError as e:
          errors[entry.name] = str(e)

  except OSError as e:
    errors['.'] = str(e)

  return DirInfo(files, dirs, ignore, errors)

