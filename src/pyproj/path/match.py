import os
import os.path as osp
import pathlib
import posixpath as pxp
import re
from collections import namedtuple

from .pattern import (
  PatternError,
  tr_glob,
  tr_path,
  tr_rel_join )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FilePattern:
  """Pattern matching similar to '.gitignore'

  .. attention::

    This is simply a container for storing information parsed from the pattern.
    It does not actually do any normalization of paths or convert windows/posix
    paths before matching, or differentiate between files and directories.
    See :meth:`FilePatterns.filter`.

  Parameters
  ----------
  pattern: str
  negate: bool
    A match to this pattern negates an existing match of the same name.
  dironly: bool
    This pattern is to only match the name of a directory.
  relative: bool
    This pattern is to match relative paths instead of just the base name.

  Notes
  -----
  * https://git-scm.com/docs/gitignore#_pattern_format
  * An optional prefix "!" which negates the pattern; any matching file excluded
    by a previous pattern will become included again. It is not possible to
    re-include a file if a parent directory of that file is excluded.
    Git doesn’t list excluded directories for performance reasons, so any
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
    pattern,
    negate = False,
    dironly = False,
    relative = False ):

    pattern = pattern.strip()
    _pattern = pattern

    if pattern.startswith('!'):
      # An optional prefix "!" which negates the pattern
      negate = True
      pattern = pattern[1:]

    elif pattern.startswith('\!'):
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

    self._pattern = _pattern
    self._pattern_tr, self._pattern_segs = tr_glob(pattern)
    self._rec = re.compile( self._pattern_tr )
    self._match = self._rec.match
    self.negate = negate
    self.dironly = dironly
    self.relative = relative

    print(f"{self._pattern} -> {self._pattern_tr}")
    print('  ' + '\n  '.join([str(seg) for seg in self._pattern_segs]))

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
  def match(self, path):
    _path = tr_path(path)
    print('match', path, '->', _path)
    return self._match(_path)

  #-----------------------------------------------------------------------------
  def match_os(self, path):
    return self.match(pathlib.PurePath(path))

  #-----------------------------------------------------------------------------
  def match_nt(self, path):
    return self.match(pathlib.PureWindowsPath(path))

  #-----------------------------------------------------------------------------
  def match_posix(self, path):
    return self.match(pathlib.PurePosixPath(path))

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FilePatterns:
  """A combination of file patters applied relative to a given 'start' directory

  Parameters
  ----------
  patterns : list[str | FilePattern]
  start : None | str | PathLike
  """
  #-----------------------------------------------------------------------------
  def __init__(self, patterns = None, start = None):
    if patterns is None:
      patterns = []

    self.patterns = [
      p if isinstance(p, FilePattern) else FilePattern(p)
      for p in patterns ]

    _start = None

    if start is not None:
      _start = tr_path(start)
      print('start', start, '->', _start)

    self.start = start
    self._start = _start

  #-----------------------------------------------------------------------------
  def filter(self, dir, fnames, dnames = None, feasible = None):
    """Filter a list of names in a directory

    Parameters
    ----------
    dir : str | PathLike
      Directory containing ``dnames`` and ``fnames``.
    fnames : list[str]
      List of file (non-directory) names in ``dir``.

    dnames : None | list[str]
      List of directory names in ``dir``.

      .. note::

        If None, any fnames ending with '/' will be used as (directory) dnames.

    feasible : None | set[str]
      The current feasible set of names (from either dnames or fnames) that have
      been matched.

    Returns
    -------
    feasible : set[str]
      Updated feasible set of matched names. It is possible that the input
      feasible set contains names that are *not* in the output if a pattern
      negates an existing match.
    """

    dir = pathlib.PurePath(dir)
    _dir = tr_path(dir)
    print('dir', dir, '->', _dir)

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

    print(f"  {self.start}, {dir}")
    print(f"    fnames: {fname_paths}")
    print(f"    dnames: {dname_paths}")

    # Can only match directories, filter out other names
    for pattern in self.patterns:
      op = feasible.difference if pattern.negate else feasible.union
      _name_paths = dname_paths if pattern.dironly else name_paths
      match = pattern._match

      if pattern.relative:
        feasible = op({ name for name, path in _name_paths if match(path) })
      else:
        feasible = op({ name for name, path in _name_paths if match(name) })

      print(f"    - {repr(pattern)} -> {feasible}")

    print(f"    {feasible}")

    return feasible


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def contains(a, b):
  return a == osp.commonpath([a, b])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def partition_dir(dir, names):
  """Separates a list of names into those that are directorys and all others.
  """
  return partition(
    lambda name: not osp.isdir(osp.join(dir, name)),
    names )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def combine_ignore_patterns(*patterns):
  """Creates a callable as ``ignore``

  Parameters
  ----------
  *patterns : FilePattern

  Returns
  -------
  callable(dir, names) -> matches
  """

  def _ignore_patterns(dir, names):
    dir = pathlib.PurePath(dir)

    print(f"dir: {dir}")

    feasible = set()

    fnames, dnames = partition_dir(dir, names)

    print(f"  dnames: {dnames}")
    print(f"  fnames: {fnames}")

    _dir = tr_path(dir)

    for pattern in patterns:
      feasible = pattern._filter(_dir, fnames, dnames, feasible)

    return feasible

  return _ignore_patterns