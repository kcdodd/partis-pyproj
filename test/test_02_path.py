import os
import os.path as osp
import tempfile
import shutil
import pathlib

from pytest import (
  raises )

from partis.pyproj import (
  PathMatcher,
  PathFilter,
  PatternError,
  partition,
  combine_ignore_patterns,
  contains )

pxp = pathlib.PurePosixPath
ntp = pathlib.PureWindowsPath
prp = pathlib.PurePath

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_partition():
  assert partition(lambda x: x > 1, [0, 1, 2]) == ([2], [0, 1])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_match_escape():
  # These test _match to check the raw string match without normalizing as a path

  # escaped special glob characters
  assert PathMatcher(r'\[]')._match('[]')
  assert PathMatcher(r'\*')._match('*')
  assert PathMatcher(r'\?')._match('?')
  assert PathMatcher(r'\*')._match('*')

  # not escaped
  assert PathMatcher(r'\.')._match(r'\.')
  assert PathMatcher(r'\abc')._match(r'\abc')
  assert PathMatcher(r'.*')._match(r'.*')
  assert PathMatcher(r'.*')._match(r'.*')
  assert PathMatcher(r'.{3}')._match(r'.{3}')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_match_chr():
  # These test _match to check the raw string match without normalizing as a path
  p = PathMatcher('a?c')
  assert p._match('abc')
  assert p._match('axc')
  assert not p._match('ac')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_match_chrset():
  # These test _match to check the raw string match without normalizing as a path
  assert PathMatcher('[!]')._match('!')
  assert not PathMatcher('[!!]')._match('!')
  assert not PathMatcher('[^!]')._match('!')
  assert PathMatcher('[]]')._match(']')
  assert not PathMatcher('[!]]')._match(']')
  assert not PathMatcher('[^]]')._match(']')
  assert PathMatcher('[]!]')._match(']')
  assert PathMatcher('[]!]')._match('!')

  assert PathMatcher('[-]')._match('-')
  assert PathMatcher('[--]')._match('-')
  assert PathMatcher('[---]')._match('-')

  assert PathMatcher('[?]')._match('?')
  assert PathMatcher('[*]')._match('*')

  p = PathMatcher('[x-z]')
  assert p._match('x')
  assert p._match('y')
  assert p._match('z')
  assert not p._match('X')
  assert not p._match('w')

  p = PathMatcher('[--0]')
  assert p._match('-')
  assert p._match('.')
  assert not p.posix('/')
  assert p._match('0')

  p = PathMatcher('[b-b]')
  assert p._match('b')
  assert not p._match('a')
  assert not p._match('c')

  # not escaped in character sets
  # bpo-409651
  p = PathMatcher(r'[\]')
  assert p._match('\\')
  assert not p._match('a')

  p = PathMatcher(r'[!\]')
  assert not p._match('\\')
  assert p._match('a')

  with raises(PatternError):
    # must be non-empty
    PathMatcher('[]')

  with raises(PatternError):
    # path separator undefined in char set
    PathMatcher('[/]')

  with raises(PatternError):
    # range is not ordered
    PathMatcher('[z-a]')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_match_any():
  p = PathMatcher('*.py')
  assert p.posix('.py')
  assert p.posix('a.py')
  assert p.posix('abc.py')
  # * does not match /
  assert not p.posix('a/.py')
  assert not p.posix('a/b/.py')

  # bpo-40480
  p = PathMatcher('*a*a*a*a*a*a*a*a*a*a')
  assert not p.posix('a' * 50 + 'b')

  # pasting multiple segments
  p = PathMatcher('*a*a/*b*b/*c*c')
  assert p.posix('_a_a_a/_b_b_b/_c_c_c')
  assert p.posix('aa/bb/cc')
  assert not p.posix('ab/bc/cd')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_match():

  p = PathMatcher('a')
  assert str(p) == 'a'
  assert not p.negate
  assert not p.dironly
  assert not p.relative
  assert p.posix('a')

  p = PathMatcher('a/')
  assert not p.negate
  assert p.dironly
  assert not p.relative
  assert p.posix('a')

  p = PathMatcher('/a')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.posix('a')

  p = PathMatcher('./a')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.posix('a')

  p = PathMatcher('!a')
  assert p.negate
  assert not p.dironly
  assert not p.relative
  assert p.posix('a')

  p = PathMatcher(r'\!a')
  assert not p.negate
  assert not p.dironly
  assert not p.relative
  assert p.posix('!a')

  p = PathMatcher('a/b')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.posix('a/b')

  p = PathMatcher('a/b/')
  assert not p.negate
  assert p.dironly
  assert p.relative
  assert p.posix('a/b')

  p = PathMatcher('!a/b')
  assert p.negate
  assert not p.dironly
  assert p.relative
  assert p.posix('a/b')

  p = PathMatcher('!a/')
  assert p.negate
  assert p.dironly
  assert not p.relative
  assert p.posix('a')

  p = PathMatcher('!a/b/')
  assert p.negate
  assert p.dironly
  assert p.relative
  assert p.posix('a/b')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_match_recurse():

  p = PathMatcher('**/foo')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.posix('a/b/foo')
  assert p.posix('a/foo')
  assert p.posix('./foo')
  assert p.posix('foo')

  p = PathMatcher('**/foo/bar')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.posix('a/b/foo/bar')
  assert p.posix('a/foo/bar')
  assert p.posix('foo/bar')

  p = PathMatcher('a/**/b')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.posix('a/b')
  assert p.posix('a/x/b')
  assert p.posix('a/x/y/b')

  p = PathMatcher('abc/**')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.posix('abc/a')
  assert p.posix('abc/a/b')

  with raises(PatternError):
    # ** only defined when bounded by /
    # e.g. **/, /**/, or /**
    p = PathMatcher('a**b')

  with raises(PatternError):
    p = PathMatcher('a**')

  with raises(PatternError):
    p = PathMatcher('**b')

  with raises(PatternError):
    p = PathMatcher('a**/b')

  with raises(PatternError):
    p = PathMatcher('**a/b')

  with raises(PatternError):
    p = PathMatcher('a/b**')

  with raises(PatternError):
    p = PathMatcher('a/**b')


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_filter():

  p = PathFilter()
  assert p.patterns == []
  assert p.start is None
  assert p.filter('.', dnames = ['a'], fnames = ['b']) == set()

  p = PathFilter(['a/', '!b'])
  assert len(p.patterns) == 2
  assert p.patterns[0].posix('a')
  assert p.patterns[1].posix('b')
  assert p.start is None
  assert p.filter('.', dnames = ['a'], fnames = ['b'], feasible = {'b'}) == {'a'}

  p = PathFilter(['x/y'], start = pxp('z'))
  assert len(p.patterns) == 1
  assert p.patterns[0].posix('x/y')
  assert p.start == pxp('z')
  assert p.filter(pxp('z/x'), dnames = [], fnames = ['y']) == {'y'}
  assert p.filter(ntp('z\\x'), dnames = [], fnames = ['y']) == {'y'}

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_file_ignore_patterns():
  ignore_patterns = combine_ignore_patterns(
    PathFilter(['a/', '!b']),
    PathFilter(['x/y'], start = pxp('z')) )

  with tempfile.TemporaryDirectory() as tmpdir:
    a = osp.join(tmpdir,'a')
    x = osp.join(tmpdir,'x')
    y = osp.join(x, 'y')

    os.mkdir(a)
    os.mkdir(x)

    with open( y, 'a'):
      os.utime( y, None )

    assert ignore_patterns('z/x', ['y'])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
if __name__ == '__main__':
  test_match_any()
