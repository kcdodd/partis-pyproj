import os
import os.path as osp
import pathlib
import posixpath as pxp
import re
from collections import namedtuple

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
    self.pattern = re.compile( self._pattern_tr )
    self.match = self.pattern.match
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

    if start is not None:
      start = posix_path(start)

    self.start = start

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

    dir = posix_path(dir)

    if dnames is None:
      dnames, fnames = partition(lambda x: x.endswith('/'), fnames)

    fnames = [d.rstrip('/') for d in fnames]
    dnames = [d.rstrip('/') for d in dnames]

    return self._filter(dir, fnames, dnames, feasible)

  #-----------------------------------------------------------------------------
  def _filter(self, dir, fnames, dnames, feasible = None):
    """Internal method, assumes dir has already been converted to posix, and
    fnames/dnames must be separatly given.
    """
    dname_paths = posix_join_rel(self.start, dir, dnames)
    fname_paths = posix_join_rel(self.start, dir, fnames)
    name_paths = dname_paths + fname_paths

    if feasible is None:
      feasible = set()

    print(f"  {self.start}")

    # Can only match directories, filter out other names
    for pattern in self.patterns:
      op = feasible.difference if pattern.negate else feasible.union
      _name_paths = dname_paths if pattern.dironly else name_paths
      match = pattern.match

      if pattern.relative:
        feasible = op({ name for name, path in _name_paths if match(path) })
      else:
        feasible = op({ name for name, path in _name_paths if match(name) })

      print(f"    {repr(pattern)} -> {feasible}")

    print(f"    {feasible}")

    return feasible

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def posix_path(path):
  return pathlib.PureWindowsPath(osp.normpath(os.fspath(path))).as_posix()

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def posix_join_rel(start, dir, names):
  """Creates paths relative to a 'start' path for a list of names in a 'dir'
  """

  rpath = pxp.relpath( dir, start = start )

  return [
    (name, pxp.normpath( pxp.join(rpath, name) ))
    for name in names ]

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
    dir = osp.normpath(os.fspath(dir))

    print(f"dir: {dir}")

    feasible = set()

    fnames, dnames = partition_dir(dir, names)

    print(f"  dnames: {dnames}")
    print(f"  fnames: {fnames}")

    dir = posix_path(dir)

    for pattern in patterns:
      feasible = pattern.filter(dir, fnames, dnames, feasible)

    return feasible

  return _ignore_patterns

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# path separator, except for a trailing recursive "/**"
re_sep = r'(?P<sep>/(?!\*\*\Z))'
# fixed (no wildcard) segment
re_fixed = r'(?P<fixed>(?:\\[*?[]|[^*?[/])+)'
# single star "*" wildcard (not double star "**") e.g. "*.txt"
re_any = r'(?P<any>(?<![\*\\])\*(?!\*))'
# single character wildcard e.g. "abc_?"
re_chr = r'(?P<chr>(?<!\\)\?)'
# character set e.g. "[a-z]"
re_chrset = r'(?P<chrset>(?<!\\)\[[!^]?\]?[^\]]*\])'
# double star sub-directory e.g. "a/**/b" or "**/b"
re_subdir = r'(?P<subdir>(?<!\\)\*\*/)'
# trailing double star e.g. "a/**"
re_alldir = r'(?P<alldir>(?<!\\)/\*\*\Z)'

re_glob = '|'.join([
  re_sep,
  re_fixed,
  re_any,
  re_chr,
  re_chrset,
  re_subdir,
  re_alldir ])

rec_glob = re.compile(re_glob)
rec_unescape = re.compile(r'\\([*?[])')

class GlobSegment(namedtuple('GlobSegment', ['ori', 'case', 'start', 'end'])):
  __slots__ = ()

  #-----------------------------------------------------------------------------
  def __str__(self):
    return f"[{self.start}:{self.end}].{self.case}:{self.ori}"

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class PatternError(ValueError):
  #-----------------------------------------------------------------------------
  def __init__(self, msg, pat, segs):
    segs = '\n  '.join([ str(seg) for seg in segs])

    msg = f"{msg}: {pat}\n  {segs}"

    super().__init__(msg)
    self.msg = msg
    self.pat = pat
    self.segs = segs

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def esc_chrset(c):
  if c == '/':
    raise ValueError("Path separator '/' in character range is undefined.")

  if c in r'\]-':
    return '\\' + c

  return c

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def tr_range(pat):

  # range
  a, _, d = pat

  _a = ord(a)
  _d = ord(d)
  _sep = ord('/')

  if _d < _a:
    raise ValueError(f"Character range is out of order: {a}-{d} -> {_a}-{_d}")

  if _a <= _sep and _sep <= _d:
    # ranges do not match forward slash '/'
    # E.G. "[--0]" matches the three characters '-', '.', '0'
    b = chr(_sep-1)
    c = chr(_sep+1)

    return ''.join([
      f"{esc_chrset(a)}-{esc_chrset(b)}" if a != b else esc_chrset(a),
      f"{esc_chrset(c)}-{esc_chrset(d)}" if d != c else esc_chrset(d) ])

  return f"{esc_chrset(a)}-{esc_chrset(d)}"

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def tr_chrset(pat):
  n = len(pat)

  if n <= 2 or pat[0] != '[' or pat[-1] != ']':
    raise ValueError(f"Character set must be non-empty: {pat}")

  wild = pat[1:-1]
  parts = ['[']
  add = parts.append

  # NOTE: a lot of this logic rests on the idea that a character class
  # cannot be an empty set. e.g. [] would not match anything, so is not allowed.
  # This means that []] is valid since the the first pair "[]" cannot close
  # a valid set.
  # Likewise, [!] cannot complement an empty set, since this would be equivalent
  # to *, meaning it should instead match "!".
  # [!] -> match "!"
  # [!!] -> match any character that is not "!"
  # []] -> match "]"
  # [!]] -> match any character that is not "]"
  # []!] -> match "]" or "!"

  # NOTE: POSIX has declared the effect of a wildcard pattern "[^...]" to be undefined.
  # Since the standard does not define this behaviour, it seems reasonable to
  # treat "^" the same as "!" due to its common meaning.

  if wild[0] in '!^' and len(wild) > 1:
    # Complement of the set of characters
    # An expression "[!...]" matches a single character, namely any
    # character that is not matched by the expression obtained by
    # removing the first '!' from it.
    add('^')
    wild = wild[1:]

  while wild:
    if len(wild) > 2 and wild[1] == '-':
      # two characters separated by '-' denote a range of characters in the set
      # defined by the ordinal
      add(tr_range(wild[:3]))
      wild = wild[3:]

    else:
      # a single character in the set
      add(esc_chrset(wild[:1]))
      wild = wild[1:]

  parts.append(']')

  return ''.join(parts)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def tr_glob(pat):
  """
  Notes
  -----
  * https://man7.org/linux/man-pages/man7/glob.7.html

  """
  segs = list()
  parts = list()
  add = parts.append

  i = 0

  for m in rec_glob.finditer(pat):

    d = [ k for k,v in m.groupdict().items() if v is not None ]
    assert len(d) == 1

    if i != m.start():
      undefined = pat[i:m.start()]
      segs.append(GlobSegment(undefined, 'undefined', i, m.start()))
      raise PatternError("Invalid pattern", pat, segs)

    segs.append(GlobSegment(m.group(0), d[0], m.start(), m.end()))

    if m['fixed']:
      # NOTE: unescape glob pattern escaped characters before applying re.escape
      # otherwise they become double-escaped
      fixed = rec_unescape.sub(r'\1', m['fixed'])
      add(re.escape(fixed))

    elif m['sep']:
      add('/')

    elif m['subdir']:
      add(r'([^/]+/)*')

    elif m['alldir']:
      add(r'(/[^/]+)+')

    elif m['any']:
      # TODO: bpo-40480, is it worth it?
      add(r'[^/]*')

    elif m['chr']:
      add(r'[^/]')

    elif m['chrset']:
      try:
        add(tr_chrset(m['chrset']))
      except ValueError as e:
        raise PatternError("Invalid pattern", pat, segs) from e

    else:
      assert False, f"Segment case undefined: {m}"

    i = m.end()

  if i != len(pat):
    undefined = pat[i:m.start()]
    segs.append(GlobSegment(undefined, 'undefined', i, len(pat)))
    raise PatternError("Invalid pattern", pat, segs)

  res = ''.join(parts)
  return fr'\A{res}\Z', segs
