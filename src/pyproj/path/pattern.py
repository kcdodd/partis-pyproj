from __future__ import annotations
import os
import os.path as osp
from pathlib import PurePath
import re
from collections import namedtuple

from .utils import _subdir

#===============================================================================
class PathPatternError(ValueError):
  pass

#===============================================================================
# NOTE: The regular expressions are constructed to match path separators defined
# by these (non-printable) control characters, unlikely to be in any filename,
# making them independent from 'os.path.sep', instead of specializing the patterns
# to each flavor.
# The paths to be matched, though, must be translated to this form.
# File Separator (E.G. '/')
SEP = chr(0x1c)
# Group Separator (E.G. '.')
CURDIR = chr(0x1d)
# Record Separator (E.G. '..')
PARDIR = chr(0x1e)

# NOTE: For debugging, uncomment for printable characters, but may also lead to
# false positive/negative matches depending on the inputs.
# SEP = '/'
# CURDIR = '.'
# PARDIR = '..'

#===============================================================================
def tr_path(path: PurePath) -> str:
  """Translates path to be compatible with the translated regex.match

  Parameters
  ---------
  path:
    Path to be translated

  Returns
  -------
  tr_path:
    Translated path, with each path segment separated by :data:`SEP`.
  """
  parts = path.parts
  anchor = path.anchor

  if not len(parts):
    return ''

  if parts[0] == anchor:
    return SEP.join(parts[1:])

  return SEP.join(parts)

#===============================================================================
def inv_path(path: str, sep: str = osp.sep) -> str:
  """Convert translated path back to os path
  """
  return sep.join(path.split(SEP))

#===============================================================================
# The glob pattern is defined using POSIX paths, even if matching other flavors
# path separator (NOTE: except for a trailing recursive "/**")
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
# NOTE: the ending '/' is consumed so the replaced pattern also matches zero times
# but leading '/' is not so that zero-length matches leave a '/' for successive
# sub-directory/file patterns.
re_subdir = r'(?P<subdir>(?<=/)\*\*/)'
re_isubdir = r'(?P<isubdir>\A\*\*/)'
# trailing double star e.g. "a/**"
re_alldir = r'(?P<alldir>/\*\*\Z)'

re_glob = '|'.join([
  re_sep,
  re_fixed,
  re_any,
  re_chr,
  re_chrset,
  re_subdir,
  re_isubdir,
  re_alldir ])

rec_glob = re.compile(re_glob)
rec_unescape = re.compile(r'\\([*?[])')

#===============================================================================
def tr_rel_join(
    start: str|None,
    dir: str,
    names: list[str],
    check: bool = True
    ) -> list[tuple[str, str]]:
  """Creates paths relative to a 'start' path for a list of names in a 'dir'
  'start' and 'dir' must already be translated by :func:`tr_path`.

  Parameters
  ----------
  start:
    Starting directory, already translated by :func:`tr_path`. If None, `dir` is
    used as-is.
  dir: str
    Directory to compute relative path to, *must* be a sub-directory of `start`,
    already translated by :func:`tr_path`.
  names:
    List of names in `dir`
  check:
    If True, raises an exception if `dir` is not a sub-directory of `start`.
    Otherwise an empty list is returned.


  Returns
  -------
  List of names joined with path relative to `start`
  """

  rpath = tr_subdir(start, dir, check=check)
  #DEBUG print(f"  rpath: {rpath}")

  if rpath is None:
    return []

  return [
    (name, tr_join(rpath, name))
    for name in names ]

#===============================================================================
def tr_join(*args: str):
  """Joins paths already translated by :func:`tr_path`.
  """
  return SEP.join([x for x in args if x])

#===============================================================================
def tr_subdir(
    start: str|None,
    path: str,
    check: bool = True
    ) -> str|None:
  """Relative path, restricted to sub-directories.

  Parameters
  ----------
  start:
    Starting directory, already translated by :func:`tr_path`. If None, `path`
    is simply returned as-is.
  path:
    Directory to compute relative path to, *must* be a sub-directory of `start`,
    already translated by :func:`tr_path`.
  check:
    If True, raises `PathPatternError` if `path` is not a sub-directory of `start`.
    Otherwise `None` is returned.

  Returns
  -------
  rpath:
    Relative path from `start` to `path`.
    `None` is returned if `check` is False and `path` was not a sub-directory of `start`.
  """

  #DEBUG print(f"  tr_subdir({start}, {path})")
  if not start:
    return path

  _start = start.split(SEP)
  _path = path.split(SEP)

  _rpath = _subdir(_start, _path)

  if _rpath is None:
    if check:
      raise PathPatternError(f"Not a subdirectory of {inv_path(start)!r}: {inv_path(path)!r}")

    return None

  return SEP.join(_rpath)

#===============================================================================
class GRef(namedtuple('GRef', ['ori', 'case', 'start', 'end'])):
  r"""Helps track how a regex was constructed from a glob pattern
  """
  __slots__ = ()


#===============================================================================
class GCase:
  r"""Container for constructing parts of a regex from glob pattern
  """
  #-----------------------------------------------------------------------------
  def __init__(self, ref: GRef|None = None):
    if ref is None:
      ref = GRef(None, 'undefined', None, None)

    self.ref = ref

  #-----------------------------------------------------------------------------
  def regex(self) -> str:
    raise NotImplementedError("")

  #-----------------------------------------------------------------------------
  def __str__(self):
    return self.regex()

#===============================================================================
class GStr(GCase):
  #-----------------------------------------------------------------------------
  def __init__(self, regex: str, ref: GRef|None = None):
    super().__init__(ref = ref)

    self._regex = regex

  #-----------------------------------------------------------------------------
  def regex(self) -> str:
    return self._regex

#===============================================================================
class GList(GCase):
  #-----------------------------------------------------------------------------
  def __init__(self, parts: list[str] = None, ref: GRef|None = None):
    super().__init__(ref = ref)

    if parts is None:
      parts = list()

    self.parts = parts

  #-----------------------------------------------------------------------------
  def regex(self) -> str:
    return ''.join([v.regex() for v in self.parts])

  #-----------------------------------------------------------------------------
  def append(self, val: str):
    self.parts.append(val)

  #-----------------------------------------------------------------------------
  def __str__(self):
    return self._regex

#===============================================================================
class GName(GStr):
  pass

#===============================================================================
class GFixed(GName):
  pass

#===============================================================================
class GChrSet(GName):
  pass

#===============================================================================
GCHR = GName(rf'[^{SEP}]')
GANY = GName(rf'[^{SEP}]*')

#===============================================================================
def reduce_any(pid, sid, n, i, working):
  r"""
  Parameters
  ----------
  pid : int
    Pattern id, may be the same for all segments, but unique among all patterns
    that might be combined.
  sid : int
    Segment id, unique only within an overall pattern.
  n : int
    Number of '*' in the segment `sid`
  i : int
    Current '*' within the segment `sid`
  working : list[GCase]
    Expressions preceeding the '*' at `i`

  Returns
  -------
  regex : str

  Notes
  -----
  Adapted according to:
  bpo-40480: "fnmatch" exponential execution time
  https://github.com/python/cpython/pull/19908
  https://github.com/python/cpython/pull/20049

  Each '*' (any) is grouped with the succeeding non-'*' into a 'lazy'
  non-capturing group.
  Since this match does not depend on the rest of the expressions, it does not
  need to backtrack to account for failures later on.
  A positive lookahead references the match and then asserts it as the
  new pattern.
  Each successive '*' group will absorb anything missed by the previous one
  until the last '*' is reached.
  The last '*' must be allowed to backtrack, since no more '*' exist to make
  up for misses (doesn't really matter if the last is 'greedy' or 'lazy').

  .. code-block:: python

    >>> p = re.compile(r'\A(?=(?P<g1>.*?A))(?P=g1)\Z')
    >>> bool(p.match('xxxA'))
    True
    >>> bool(p.match('xxxAxxxA'))
    False

  This fails because a lazy match to the first 'xxxA' misses the second 'xxxA'.
  For 3 '*', there should be 2 lazy+lookahead, and the last will be unconditional

  .. code-block::

          n: 3
    pattern: ...*...*...*...
          i:    0   1   2   3
    working: 000 111 222 333
     groups:    [  ][  ]

  Groups are named according to ``f'p{pid}s{sid}g{i-1}'``.

  """

  pat = ''.join([v.regex() for v in working])

  if i > 0:
    # This call is actually adding the i-1 group
    # NOTE: i==0 (and n==0) simply returns the preceeding working pattern, since
    # there is not a -1 group

    if i == n:
      # NOTE: i==n means this is the final call, but the n-1 '*' should
      # *not* have a lazy+lookahead group.
      # this also means that for n==1, this will be the only translated '*'.
      pat = rf'{GANY}{pat}'
    else:
      name = f'p{pid}s{sid}g{i-1}'
      pat = rf'(?=(?P<{name}>{GANY}?{pat}))(?P={name})'

  return pat

#===============================================================================
class GSegment(GList):
  #-----------------------------------------------------------------------------
  def __init__(self, pid, sid, parts = None, ref = None):
    super().__init__(parts = parts, ref = ref)
    self.pid = pid
    self.sid = sid

  #-----------------------------------------------------------------------------
  def regex(self):
    if not self.parts:
      return ''

    # collapse repeated '*' and count
    n = int(self.parts[0] is GANY)
    parts = [self.parts[0]]

    for v in self.parts:
      isany = v is GANY

      if not (isany and parts[-1] is GANY):
        parts.append(v)
        n += int(isany)

    # construct groups
    i = 0
    combined = list()
    working = list()

    for v in self.parts:
      if v is GANY:
        combined.append(reduce_any(self.pid, self.sid, n, i, working))
        working = list()
        i += 1
      else:
        working.append(v)

    combined.append(reduce_any(self.pid, self.sid, n, i, working))

    return ''.join(combined)

#===============================================================================
class GSeparator(GStr):
  pass

GSEP = GSeparator(SEP)
GSUBDIR = GSeparator(rf'([^{SEP}]+{SEP})*')
GALLDIR = GSeparator(rf'({SEP}[^{SEP}]+)+')

#===============================================================================
class GPath(list):
  def regex(self):
    return ''.join([v.regex() for v in self])

#===============================================================================
class PatternError(ValueError):
  #-----------------------------------------------------------------------------
  def __init__(self, msg, pat, segs):
    segs = '\n  '.join([ str(seg) for seg in segs])

    msg = f"{msg}: {pat}\n  {segs}"

    super().__init__(msg)
    self.msg = msg
    self.pat = pat
    self.segs = segs

#===============================================================================
def esc_chrset(c):
  if c == '/':
    raise PathPatternError("Path separator '/' in character range is undefined.")

  if c in r'\]-':
    return '\\' + c

  return c

#===============================================================================
def tr_range(pat):

  # range
  a, _, d = pat

  _a = ord(a)
  _d = ord(d)
  _sep = ord('/')

  if _d < _a:
    raise PathPatternError(f"Character range is out of order: {a}-{d} -> {_a}-{_d}")

  if _a <= _sep and _sep <= _d:
    # ranges do not match forward slash '/'
    # E.G. "[--0]" matches the three characters '-', '.', '0'
    b = chr(_sep-1)
    c = chr(_sep+1)

    return ''.join([
      f"{esc_chrset(a)}-{esc_chrset(b)}" if a != b else esc_chrset(a),
      f"{esc_chrset(c)}-{esc_chrset(d)}" if d != c else esc_chrset(d) ])

  return f"{esc_chrset(a)}-{esc_chrset(d)}"

#===============================================================================
def tr_chrset(pat):
  n = len(pat)

  if n <= 2 or pat[0] != '[' or pat[-1] != ']':
    raise PathPatternError(f"Character set must be non-empty: {pat}")

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

#===============================================================================
def tr_glob(pat, pid = 0) -> tuple[str, list[GRef]]:
  """
  Notes
  -----
  * https://man7.org/linux/man-pages/man7/glob.7.html

  """

  # collapse repeated separators '//...' to single '/'
  pat = re.sub(r'/+', '/', pat)

  refs = []

  if pat == '**':
    return r'\A.*\Z', refs

  segs = GPath()

  def add(case):
    if isinstance(case, GSeparator):
      segs.append(case)
      return

    if not ( len(segs) and isinstance(segs[-1], GSegment) ):
      segs.append(GSegment(pid = pid, sid = len(segs)))

    segs[-1].append(case)


  i = 0
  m = None

  for m in rec_glob.finditer(pat):

    d = [ k for k,v in m.groupdict().items() if v is not None ]
    assert len(d) == 1

    if i != m.start():
      undefined = pat[i:m.start()]
      refs.append(GRef(undefined, 'undefined', i, m.start()))
      raise PatternError("Invalid pattern", pat, refs)

    refs.append(GRef(m.group(0), d[0], m.start(), m.end()))

    if m['fixed']:
      # NOTE: unescape glob pattern 'escaped' characters before applying re.escape
      # otherwise they become double-escaped
      fixed = rec_unescape.sub(r'\1', m['fixed'])
      add(GFixed(re.escape(fixed)))

    elif m['sep']:
      add(GSEP)

    elif m['subdir'] or m['isubdir']:
      add(GSUBDIR)

    elif m['alldir']:
      add(GALLDIR)

    elif m['any']:
      add(GANY)

    elif m['chr']:
      add(GCHR)

    elif m['chrset']:
      try:
        add(GChrSet(tr_chrset(m['chrset'])))
      except ValueError as e:
        raise PatternError("Invalid pattern", pat, refs) from e

    else:
      assert False, f"Segment case undefined: {m}"

    i = m.end()

  if i != len(pat):
    undefined = pat[i:]
    refs.append(GRef(undefined, 'undefined', i, len(pat)))
    raise PatternError("Invalid pattern", pat, refs)

  #DEBUG print(segs)
  res = segs.regex()
  return fr'\A{res}\Z', refs
