import os
import os.path as osp
import tempfile
import shutil

from pytest import (
  raises )

from partis.pyproj import (
  FilePattern,
  FilePatterns,
  partition,
  combine_ignore_patterns,
  contains )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_partition():
  assert partition(lambda x: x > 1, [0, 1, 2]) == ([2], [0, 1])

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

  p = FilePattern('!a')
  assert p.negate
  assert not p.dironly
  assert not p.relative
  assert p.match('a')

  p = FilePattern('\!a')
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
def test_file_patterns():

  p = FilePatterns()
  assert p.patterns == []
  assert p.start == None
  assert p.filter('.', ['a'], ['b']) == set()

  p = FilePatterns(['a/', '!b'])
  assert len(p.patterns) == 2
  assert p.patterns[0].match('a')
  assert p.patterns[1].match('b')
  assert p.start == None
  assert p.filter('.', ['a'], ['b'], feasible = {'b'}) == {'a'}

  p = FilePatterns(['x/y'], start = 'z')
  assert len(p.patterns) == 1
  assert p.patterns[0].match('x/y')
  assert p.start == 'z'
  assert p.filter('z/x', [], ['y']) == {'y'}

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
