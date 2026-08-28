from __future__ import annotations
import sys
import re
import unicodedata

#===============================================================================
# Unicode general categories that are stripped from package meta-data.
# NOTE: this is narrower than ``str.isprintable()``, which also excludes the
# format characters (Cf) and the non-space separators (Zs). Those are needed by
# legitimate text: e.g. U+200D ZERO WIDTH JOINER in emoji sequences, U+200C
# ZERO WIDTH NON-JOINER in Persian and Indic scripts, and U+00A0 NO-BREAK SPACE.
# The categories kept here are the ones that are either un-encodable, un-typeable,
# or hazardous in an RFC 822 header:
# * Cc control characters (which are also header injection vectors)
# * Cs surrogates (not encodable as UTF-8)
# * Co private use, Cn unassigned (no defined meaning)
# * Zl, Zp line and paragraph separators (line boundaries for ``str.splitlines``)
STRIP_CATEGORIES = frozenset(['Cc', 'Cs', 'Co', 'Cn', 'Zl', 'Zp'])

#===============================================================================
def _strip_char(c):
  return c not in '\n\t' and unicodedata.category(c) in STRIP_CATEGORIES

#===============================================================================
def _gen_nonprintable():
  test = []

  ns = [ [0,], ]

  for i in range(1, sys.maxunicode+1):
    c = chr(i)
    test.append(c)

    if _strip_char(c):
      n = ns[-1]

      if i == n[-1] + 1:
        if len(n) == 1:
          n.append(i)
        else:
          n[-1] = i
      else:
        ns.append([i,])

  test = ''.join(test)

  # print(len(test), test.isprintable())
  # print(len(ns))
  # print(ns)

  return ns, test

#===============================================================================
def gen_nonprintable():
  """Method used to generate a regex for matching all unicode characters in
  :data:`STRIP_CATEGORIES`, except for newlines '\\n' and tabs '\\t'.
  """
  ns, test = _gen_nonprintable()

  def fmt(i):
    if i < 2**8:
      return rf'\x{i:02X}'
    elif i < 2**16:
      return rf'\u{i:04X}'
    else:
      return rf'\U{i:08X}'

  # format character ranges as unicode literals
  ns = [
    fmt(n[0]) if len(n) == 1 else ( fmt(n[0]) + '-' + fmt(n[-1]) )
    for n in ns ]

  nonprintable = "  r'["
  _nonprintable = '['

  line_max = 75
  line_len = len(nonprintable)

  for n in ns:
    if line_len + len(n) > line_max:
      nonprintable += "'\n  r'"
      line_len = 0

    nonprintable += n
    _nonprintable += n
    line_len += len(n)

  nonprintable += "]'"
  _nonprintable += ']'

  _nonprintable = re.compile(
    _nonprintable.encode('utf-8').decode('unicode_escape'),
    re.UNICODE )

  test = _nonprintable.sub('', test)
  test = re.sub(r'[\t\n]', '', test)

  assert not any( _strip_char(c) for c in test )

  return nonprintable

#===============================================================================
if __name__ == '__main__':
  print( gen_nonprintable() )
