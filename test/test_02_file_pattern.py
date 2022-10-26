import os
import os.path as osp
import tempfile
import shutil
import pathlib

from pytest import (
  raises )

from partis.pyproj import (
  FilePattern,
  FilePatterns,
  PatternError,
  partition,
  combine_ignore_patterns,
  contains )

pxp = pathlib.PurePosixPath
ntp = pathlib.PureWindowsPath

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_partition():
  assert partition(lambda x: x > 1, [0, 1, 2]) == ([2], [0, 1])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_file_pattern_escape():
  # escaped special glob characters
  assert FilePattern(r'\[]').match('[]')
  assert FilePattern(r'\*').match('*')
  assert FilePattern(r'\?').match('?')
  assert FilePattern(r'\*').match('*')

  # not escaped
  assert FilePattern(r'\.').match(r'\.')
  assert FilePattern(r'\abc').match(r'\abc')
  assert FilePattern(r'.*').match(r'.*')
  assert FilePattern(r'.*').match(r'.*')
  assert FilePattern(r'.{3}').match(r'.{3}')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_file_pattern():

  p = FilePattern('a')
  assert str(p) == 'a'
  assert not p.negate
  assert not p.dironly
  assert not p.relative
  assert p.match('a')

  p = FilePattern('a/')
  assert not p.negate
  assert p.dironly
  assert not p.relative
  assert p.match('a')

  p = FilePattern('/a')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.match('a')

  p = FilePattern('!a')
  assert p.negate
  assert not p.dironly
  assert not p.relative
  assert p.match('a')

  p = FilePattern(r'\!a')
  assert not p.negate
  assert not p.dironly
  assert not p.relative
  assert p.match('!a')

  p = FilePattern('a/b')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.match('a/b')

  p = FilePattern('a/b/')
  assert not p.negate
  assert p.dironly
  assert p.relative
  assert p.match('a/b')

  p = FilePattern('!a/b')
  assert p.negate
  assert not p.dironly
  assert p.relative
  assert p.match('a/b')

  p = FilePattern('!a/')
  assert p.negate
  assert p.dironly
  assert not p.relative
  assert p.match('a')

  p = FilePattern('!a/b/')
  assert p.negate
  assert p.dironly
  assert p.relative
  assert p.match('a/b')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_file_pattern_recurse():

  p = FilePattern('**/foo')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.match('a/b/foo')
  assert p.match('a/foo')
  assert p.match('./foo')
  assert p.match('foo')

  p = FilePattern('**/foo/bar')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.match('a/b/foo/bar')
  assert p.match('a/foo/bar')
  assert p.match('foo/bar')

  p = FilePattern('a/**/b')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.match('a/b')
  assert p.match('a/x/b')
  assert p.match('a/x/y/b')

  p = FilePattern('abc/**')
  assert not p.negate
  assert not p.dironly
  assert p.relative
  assert p.match('abc/a')
  assert p.match('abc/a/b')

  with raises(PatternError):
    # ** only defined when bounded by /
    # e.g. **/, /**/, or /**
    p = FilePattern('a**b')

  with raises(PatternError):
    p = FilePattern('a**')

  with raises(PatternError):
    p = FilePattern('**b')

  with raises(PatternError):
    p = FilePattern('a**/b')

  with raises(PatternError):
    p = FilePattern('**a/b')

  with raises(PatternError):
    p = FilePattern('a/b**')

  with raises(PatternError):
    p = FilePattern('a/**b')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_file_pattern_any():
  p = FilePattern('*.py')
  assert p.match('.py')
  assert p.match('a.py')
  assert p.match('abc.py')
  # * does not match /
  assert not p.match('a/.py')
  assert not p.match('a/b/.py')

  # TODO: bpo-40480, is it worth it?
  # p = FilePattern('*a*a*a*a*a*a*a*a*a*a')
  # assert not p.match('a' * 50 + 'b')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_file_pattern_chr():
  # These test _match to check the raw string match without normalizing as a path
  p = FilePattern('a?c')
  assert p._match('abc')
  assert p._match('axc')
  assert not p._match('ac')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_file_pattern_chrset():
  # These test _match to check the raw string match without normalizing as a path
  assert FilePattern('[!]')._match('!')
  assert not FilePattern('[!!]')._match('!')
  assert not FilePattern('[^!]')._match('!')
  assert FilePattern('[]]')._match(']')
  assert not FilePattern('[!]]')._match(']')
  assert not FilePattern('[^]]')._match(']')
  assert FilePattern('[]!]')._match(']')
  assert FilePattern('[]!]')._match('!')

  assert FilePattern('[-]')._match('-')
  assert FilePattern('[--]')._match('-')
  assert FilePattern('[---]')._match('-')

  assert FilePattern('[?]')._match('?')
  assert FilePattern('[*]')._match('*')

  p = FilePattern('[x-z]')
  assert p._match('x')
  assert p._match('y')
  assert p._match('z')
  assert not p._match('X')
  assert not p._match('w')

  p = FilePattern('[--0]')
  assert p._match('-')
  assert p._match('.')
  assert not p._match('/')
  assert p._match('0')

  p = FilePattern('[b-b]')
  assert p._match('b')
  assert not p._match('a')
  assert not p._match('c')

  # not escaped in character sets
  # bpo-409651
  p = FilePattern(r'[\]')
  assert p._match('\\')
  assert not p._match('a')

  p = FilePattern(r'[!\]')
  assert not p._match('\\')
  assert p._match('a')

  with raises(PatternError):
    # must be non-empty
    FilePattern('[]')

  with raises(PatternError):
    # path separator undefined in char set
    FilePattern('[/]')

  with raises(PatternError):
    # range is not ordered
    FilePattern('[z-a]')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_file_patterns():

  p = FilePatterns()
  assert p.patterns == []
  assert p.start == None
  assert p.filter('.', dnames = ['a'], fnames = ['b']) == set()

  p = FilePatterns(['a/', '!b'])
  assert len(p.patterns) == 2
  assert p.patterns[0].match('a')
  assert p.patterns[1].match('b')
  assert p.start == None
  assert p.filter('.', dnames = ['a'], fnames = ['b'], feasible = {'b'}) == {'a'}

  p = FilePatterns(['x/y'], start = 'z')
  assert len(p.patterns) == 1
  assert p.patterns[0].match('x/y')
  assert p.start == 'z'
  assert p.filter('z/x', dnames = [], fnames = ['y']) == {'y'}
  assert p.filter('z\\x', dnames = [], fnames = ['y']) == {'y'}

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_file_ignore_patterns():
  ignore_patterns = combine_ignore_patterns(
    FilePatterns(['a/', '!b']),
    FilePatterns(['x/y'], start = 'z') )

  with tempfile.TemporaryDirectory() as tmpdir:
    a = osp.join(tmpdir,'a')
    x = osp.join(tmpdir,'x')
    y = osp.join(x, 'y')

    os.mkdir(a)
    os.mkdir(x)

    with open( y, 'a'):
      os.utime( y, None )

    assert ignore_patterns('z/x', ['y'])
