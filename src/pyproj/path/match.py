from __future__ import annotations
import os.path as osp
from os import PathLike
import pathlib
from pathlib import (
  PurePath,
  PureWindowsPath,
  PurePosixPath )
import re

from .pattern import (
  PatternError,
  tr_glob,
  tr_path,
  tr_rel_join )

#===============================================================================
class PathMatcher:
  r"""Pattern matching similar to '.gitignore'

  Parameters
  ----------
  pattern:
    See notes below on pattern formatting.
  negate:
    A match to this pattern negates an existing match of the same name.
  dironly:
    This pattern is to only match the name of a directory.
  relative:
    This pattern is to match relative paths instead of just the base name.

  Notes
  -----
  * https://git-scm.com/docs/gitignore#_pattern_format
  * An optional prefix "!" which negates the pattern; any matching file excluded
    by a previous pattern will become included again. It is not possible to
    re-include a file if a parent directory of that file is excluded.
    Git doesn't list excluded directories for performance reasons, so any
    patterns on contained files have no effect, no matter where they are defined.
    Put a backslash ("\") in front of the first "!" for patterns that begin with
    a literal "!", for example, "\!important!.txt".
  * The slash / is used as the directory separator. Separators may occur at the
    beginning, middle or end of the .gitignore search pattern.
  * If there is a separator at the beginning or middle (or both) of the pattern,
    then the pattern is relative to the directory level of the particular
    .gitignore file itself. Otherwise the pattern may also match at any level
    below the .gitignore level.
  * If there is a separator at the end of the pattern then the pattern will only
    match directories, otherwise the pattern can match both files and directories.
  * For example, a pattern doc/frotz/ matches doc/frotz directory, but not
    a/doc/frotz directory; however frotz/ matches frotz and a/frotz that is a
    directory (all paths are relative from the .gitignore file).
  * An asterisk "*" matches anything except a slash. The character "?" matches
    any one character except "/".
  * The range notation, e.g. [a-zA-Z], can be used
    to match one of the characters in a range. See fnmatch(3) and the FNM_PATHNAME
    flag for a more detailed description.
    This logic rests on the idea that a character class
    cannot be an empty set. e.g. [] would not match anything, so is not allowed.
    This means that []] is valid since the the first pair "[]" cannot close
    a valid set.
    Likewise, [!] cannot complement an empty set, since this would be equivalent
    to *, meaning it should instead match "!".
    [!] -> match "!"
    [!!] -> match any character that is not "!"
    []] -> match "]"
    [!]] -> match any character that is not "]"
    []!] -> match "]" or "!"
  * Two consecutive asterisks ("**") in patterns matched against full pathname
    may have special meaning:
  * A leading "**" followed by a slash means match in all directories. For example,
    "**/foo" matches file or directory "foo" anywhere, the same as pattern "foo".
    "**/foo/bar" matches file or directory "bar" anywhere that is directly under
    directory "foo".
  * A trailing "/**" matches everything inside. For example, "abc/**" matches all
    files inside directory "abc", relative to the location of the .gitignore file,
    with infinite depth.
  * A slash followed by two consecutive asterisks then a slash matches zero or
    more directories. For example, "a/**/b" matches "a/b", "a/x/b", "a/x/y/b"
    and so on.
  * The meta-characters "*", "?", and "[" may be escaped by backslash.

  """
  #-----------------------------------------------------------------------------
  def __init__(self,
    pattern: str,
    negate: bool = False,
    dironly: bool = False,
    relative: bool = False):

    pattern = str(pattern).strip()
    _pattern = pattern

    if pattern.startswith('!'):
      # An optional prefix "!" which negates the pattern
      negate = True
      pattern = pattern[1:]

    elif pattern.startswith(r'\!'):
      # Put a backslash ("\") in front of the first "!" for patterns that begin
      # with a literal "!", for example, "\!important!.txt".
      pattern = pattern[1:]

    if pattern.endswith('/'):
      # If there is a separator at the end of the pattern then the pattern will
      # only match directories
      dironly = True
      pattern = pattern[:-1]

    if pattern.count('/') > 0:
      # If there is a separator at the beginning or middle (or both) of the
      # pattern, then the pattern is relative to the directory level of the
      # particular .gitignore file itself.
      relative = True

      if pattern.startswith('/'):
        pattern = pattern[1:]

      elif pattern.startswith('./'):
        pattern = pattern[2:]

    self._pattern = _pattern
    self._pattern_tr, self._pattern_segs = tr_glob(pattern)
    self._rec = re.compile( self._pattern_tr )
    self._match = self._rec.match
    self.negate = negate
    self.dironly = dironly
    self.relative = relative

    #DEBUG print(f"{self._pattern} -> {self._pattern_tr}")
    #DEBUG print('  ' + '\n  '.join([str(seg) for seg in self._pattern_segs]))

  #-----------------------------------------------------------------------------
  def __str__(self):
    return self._pattern

  #-----------------------------------------------------------------------------
  def __repr__(self):
    args = [f"'{self._pattern}'"]

    for attr in ['negate', 'dironly', 'relative']:
      if getattr(self, attr):
        args.append(f'{attr} = True')

    args = ', '.join(args)

    return f"{type(self).__name__}({args})"

  #-----------------------------------------------------------------------------
  def match(self, path: PathLike) -> bool:
    """
    Parameters
    ----------
    path:

    Returns
    -------
    matched :
      True if the ``path`` matches this pattern

    """

    if not isinstance(path, PurePath):
      path = PurePath(path)

    _path = tr_path(path)
    #DEBUG print('match', path, '->', _path)
    return self._match(_path)

  #-----------------------------------------------------------------------------
  __call__ = match

  #-----------------------------------------------------------------------------
  def nt(self, path: PathLike) -> bool:
    """Convenience method to force match as a Windows path
    """
    return self(PureWindowsPath(path))

  #-----------------------------------------------------------------------------
  def posix(self, path: PathLike) -> bool:
    """Convenience method to force match as a POSIX path
    """
    return self(PurePosixPath(path))

#===============================================================================
class PathFilter:
  """A combination of file patters applied relative to a given 'start' directory

  Parameters
  ----------
  patterns:
  start:
  """
  #-----------------------------------------------------------------------------
  def __init__(self,
      patterns: list[str|PathMatcher] = None,
      start: PathLike|None = None):

    if patterns is None:
      patterns = []

    self.patterns = [
      p if isinstance(p, PathMatcher) else PathMatcher(p)
      for p in patterns ]

    _start = None

    if start is not None:
      if not isinstance(start, PurePath):
        start = PurePath(start)

      _start = tr_path(start)
      #DEBUG print('start', start, '->', _start)

    self.start = start
    self._start = _start

  #-----------------------------------------------------------------------------
  def filter(self,
      dir: PathLike,
      fnames: list[str],
      dnames: list[str]|None = None,
      feasible: set[str]|None = None) -> set[str]:
    """Filter a list of names in a directory

    Parameters
    ----------
    dir:
      Directory containing ``dnames`` and ``fnames``.
    fnames:
      List of file (non-directory) names in ``dir``.
    dnames:
      List of directory names in ``dir``.

      .. note::

        If None, any fnames ending with '/' will be used as (directory) dnames.

    feasible:
      The current feasible set of names (from either dnames or fnames) that have
      been matched.

    Returns
    -------
    feasible:
      Updated feasible set of matched names. It is possible that the input
      feasible set contains names that are *not* in the output if a pattern
      negates an existing match.
    """

    if not isinstance(dir, PurePath):
      dir = PurePath(dir)

    _dir = tr_path(dir)
    #DEBUG print('dir', dir, '->', _dir)

    if dnames is None:
      dnames, fnames = partition(lambda x: x.endswith(osp.sep), fnames)

    fnames = [d.rstrip(osp.sep) for d in fnames]
    dnames = [d.rstrip(osp.sep) for d in dnames]

    return self._filter(_dir, fnames, dnames, feasible)

  #-----------------------------------------------------------------------------
  def _filter(self, dir, fnames, dnames, feasible = None):
    """Internal method, assumes dir has already been converted to posix, and
    fnames/dnames must be separatly given.
    """
    dname_paths = tr_rel_join(self._start, dir, dnames)
    fname_paths = tr_rel_join(self._start, dir, fnames)
    name_paths = dname_paths + fname_paths

    if feasible is None:
      feasible = set()

    #DEBUG print(f"  {self.start}, {dir}")
    #DEBUG print(f"    fnames: {fname_paths}")
    #DEBUG print(f"    dnames: {dname_paths}")

    # Can only match directories, filter out other names
    for pattern in self.patterns:
      op = feasible.difference if pattern.negate else feasible.union
      _name_paths = dname_paths if pattern.dironly else name_paths
      match = pattern._match

      if pattern.relative:
        feasible = op({ name for name, path in _name_paths if match(path) })
      else:
        feasible = op({ name for name, path in _name_paths if match(name) })

      #DEBUG print(f"    - {repr(pattern)} -> {feasible}")

    #DEBUG print(f"    {feasible}")

    return feasible


#===============================================================================
def contains(a, b):
  a = str(a)
  b = str(b)
  return a == osp.commonpath([a, b])

#===============================================================================
def partition(test, vals):
  """Separates a single list into two lists

  Parameters
  ----------
  test : callable
  vals : list

  Returns
  -------
  x, y: (list, list)
    The first list contains elememts of ``vals`` where ``test`` returned true.
    The second list contains all other elements.
  """
  x = list()
  y = list()

  for val in vals:
    if test(val):
      x.append(val)
    else:
      y.append(val)

  return x, y

#===============================================================================
def partition_dir(dir, names):
  """Separates a list of names into those that are directorys and all others.
  """
  return partition(
    lambda name: not osp.isdir(osp.join(dir, name)),
    names )

#===============================================================================
def combine_ignore_patterns(*patterns):
  """Creates a callable as ``ignore``

  Parameters
  ----------
  *patterns : PathMatcher

  Returns
  -------
  callable(dir, names) -> matches
  """
  # TODO: implement as callable object instead of closure for possible inspection

  def _ignore_patterns(dir, names):
    dir = PurePath(dir)

    #DEBUG print(f"dir: {dir}")

    feasible = set()

    fnames, dnames = partition_dir(dir, names)

    #DEBUG print(f"  dnames: {dnames}")
    #DEBUG print(f"  fnames: {fnames}")

    _dir = tr_path(dir)

    for pattern in patterns:
      feasible = pattern._filter(_dir, fnames, dnames, feasible)

    return feasible

  return _ignore_patterns
