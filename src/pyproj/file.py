from __future__ import annotations
import os

#===============================================================================
def tail(path, n, bufsize = 1024, encoding = 'utf-8'):
  """Reads the last n lines from a file

  Parameters
  ----------
  path : str
  n : int
    Max number of lines to read from the end of the file
  bufsize : int
    Number of bytes to buffer at a time.

  Returns
  -------
  lines : List[str]
    Up to ``n`` lines from the end of the file
  """

  bufsize = int(bufsize)
  bufsize = max(1, bufsize)

  n = int(n)
  n = max( 0, n )

  buf = bytes()
  nlines = 0

  head = 0

  with open( path, 'rb' ) as fp:
    # total number of bytes in the file
    tot = fp.seek( 0, os.SEEK_END )

    head = tot

    while nlines < n and head > 0:
      # NOTE: the number of newline characters is one less than number of 'lines'
      nread = min( head, bufsize )
      head -= nread

      fp.seek( head, os.SEEK_SET )

      _buf = fp.read( nread )

      # NOTE: this is not exact, since pairs of '\r\n' may happen on the read
      # boundary, but should count approximately the number of LF, CR, and CR+LF.
      # LF -> 1 + 0 + 0 = 1
      # CR -> 0 + 1 + 0 = 1
      # CR+LF -> 1 + 1 - 1 = 1
      nlines += _buf.count(b'\n') + _buf.count(b'\r') - _buf.count(b'\r\n')

      buf = _buf + buf

  if nlines > 0 and head > 0:
    # remove everything before first newline to ensure only complete lines are kept
    i = buf.index(b'\n')
    buf = buf[(i+1):]

  res = buf.decode(encoding, errors = 'replace')
  lines = res.split('\n')[-n:]

  return lines
