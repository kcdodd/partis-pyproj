from __future__ import annotations
import sys
import re

#===============================================================================
def _gen_nonprintable():
  test = []

  ns = [ [0,], ]

  for i in range(1, sys.maxunicode+1):
    c = chr(i)
    test.append(c)

    if not ( c.isprintable() or c in '\n\t' ):
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
  """Method used to generate a regex for matchiing all non-printable unicode
  characters, except for newlines '\\n' and tabs '\\t'.
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

  # print( len(test), test.isprintable() )

  assert( test.isprintable() )

  return nonprintable

#===============================================================================
if __name__ == '__main__':
  print( gen_nonprintable() )
