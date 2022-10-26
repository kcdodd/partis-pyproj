import os
import os.path as osp
import re
from collections import namedtuple

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# SEP = chr(0x1c)
SEP = '◆'
CURDIR = chr(0x1d)
PARDIR = chr(0x1e)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def tr_rel_join(start, dir, names):
  """Creates paths relative to a 'start' path for a list of names in a 'dir'
  """

  rpath = tr_subdir( start, dir )
  print(f"  rpath: {rpath}")

  return [
    (name, tr_join(rpath, name))
    for name in names ]

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def tr_join(*args):
  args = [x for x in args if x]

  return SEP.join(args)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def tr_subdir(start, path):
  print(f"  tr_subdir({start}, {path})")
  if not start:
    return path

  _start = start.split(SEP)
  _path = path.split(SEP)

  if len(_start) > len(_path):
    raise ValueError(f"Not a subdirectory of {itr_path(start)}: {itr_path(path)}")

  for i, (p, s) in enumerate(zip(_path, _start)):
    print(f"    {i}: {p} != {s} ({p != s})")
    if p != s:
      return SEP.join(_path[i:])

  return SEP.join(_path[i+1:])


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def tr_path(path):

  parts = path.parts
  anchor = path.anchor

  if not len(parts):
    return ''

  if parts[0] == anchor:
    return SEP.join(parts[1:])

  return SEP.join(parts)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def itr_path(path):
  return osp.sep.join(path.split(SEP))


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GRef(namedtuple('GRef', ['ori', 'case', 'start', 'end'])):
  __slots__ = ()


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GCase:
  #-----------------------------------------------------------------------------
  def __init__(self, ref = None):
    if ref is None:
      ref = GRef(None, 'undefined', None, None)

    self.ref = ref

  #-----------------------------------------------------------------------------
  def regex(self):
    raise NotImplementedError("")

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GStr(GCase):
  #-----------------------------------------------------------------------------
  def __init__(self, regex, ref = None):
    super().__init__(ref = ref)

    self._regex = regex

  #-----------------------------------------------------------------------------
  def regex(self):
    return self._regex

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GList(GCase):
  #-----------------------------------------------------------------------------
  def __init__(self, parts = None, ref = None):
    super().__init__(ref = ref)

    if parts is None:
      parts = list()

    self.parts = parts

  #-----------------------------------------------------------------------------
  def regex(self):
    return ''.join([v.regex() for v in self.parts])

  #-----------------------------------------------------------------------------
  def append(self, val):
    self.parts.append(val)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GName(GStr):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GFixed(GName):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GChrSet(GName):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
GCHR = GName(rf'[^{SEP}]')
GANY = GName(rf'[^{SEP}]*')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def reduce_any(i, n, working):
  pat = ''.join([v.regex() for v in working])

  if i == n-1:
    pat = rf'{GANY}{pat}'
  elif i > 0:
    pat = rf'(?=(?P<g{i-1}>{GANY}?{pat}))(?P=g{i-1})'

  return pat

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GSegment(GList):
  pass

  # #-----------------------------------------------------------------------------
  # def regex(self):

  #   n = sum(v is GANY for v in self)
  #   i = 0
  #   combined = list()
  #   working = list()

  #   for v in self:
  #     if v is GANY:
  #       combined.append(reduce_any(i, n, working))
  #       working = list()
  #       i += 1
  #     else:
  #       working.append(v)

  #   combined.append(reduce_any(i, n, working))

  #   return ''.join(combined)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GSeparator(GStr):
  pass

GSEP = GSeparator(SEP)
GSUBDIR = GSeparator(rf'([^{SEP}]+{SEP})*')
GALLDIR = GSeparator(rf'({SEP}[^{SEP}]+)+')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class GPath(list):
  def regex(self):
    return ''.join([v.regex() for v in self])

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

  # collapse repeated separators '//...' to single '/'
  pat = re.sub(r'/+', '/', pat)

  refs = list()
  segs = GPath()

  def add(case):
    if isinstance(case, GSeparator):
      segs.append(case)
      return

    if not ( len(segs) and isinstance(segs[-1], GSegment) ):
      segs.append(GSegment())

    segs[-1].append(case)


  i = 0

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
      # TODO: bpo-40480, is it worth it?
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
    undefined = pat[i:m.start()]
    refs.append(GRef(undefined, 'undefined', i, len(pat)))
    raise PatternError("Invalid pattern", pat, refs)

  print(segs)
  res = segs.regex()
  return fr'\A{res}\Z', refs
