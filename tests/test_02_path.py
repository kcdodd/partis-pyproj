import os
import os.path as osp
import tempfile
import shutil
import pathlib
from pathlib import Path, PurePath

from pytest import (
  raises )

from partis.pyproj import (
  PathMatcher,
  PathFilter,
  PatternError,
  partition,
  combine_ignore_patterns,
  contains )

from partis.pyproj.path.pattern import (
  tr_path,
  inv_path,
  PatternError)

from partis.pyproj.path.utils import (
  _concretize,
  _subdir,
  file_size_mtime)

from partis.pyproj.path import (
  PathError,
  subdir,
  git_tracked_mtime)

pxp = pathlib.PurePosixPath
ntp = pathlib.PureWindowsPath
prp = pathlib.PurePath

#===============================================================================
def test_translate():
  path = 'a/b/c'
  _path = tr_path(pxp(path))
  assert inv_path(_path, sep='/') == path

#===============================================================================
def test_partition():
  assert partition(lambda x: x > 1, [0, 1, 2]) == ([2], [0, 1])

#===============================================================================
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

#===============================================================================
def test_match_chr():
  # These test _match to check the raw string match without normalizing as a path
  p = PathMatcher('a?c')
  assert p._match('abc')
  assert p._match('axc')
  assert not p._match('ac')

#===============================================================================
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

#===============================================================================
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

#===============================================================================
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

#===============================================================================
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


#===============================================================================
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

#===============================================================================
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

#===============================================================================
# path/utils.py — _concretize
#===============================================================================
def test_concretize_empty_component():
  assert _concretize(['', 'a', 'b']) == ['a', 'b']

def test_concretize_curdir_component():
  assert _concretize(['.', 'a']) == ['a']
  assert _concretize(['a', '.', 'b']) == ['a', 'b']

def test_concretize_pardir_past_root():
  # 'a/../../b' requires knowing a's parent — not concretizable
  assert _concretize(['a', '..', '..', 'b']) is None

def test_concretize_pardir_within_root():
  # 'a/../b' → 'b' is fine
  assert _concretize(['a', '..', 'b']) == ['b']

#===============================================================================
# path/utils.py — _subdir
#===============================================================================
def test_subdir_internal_nonconcretizable_start():
  # start path cannot be concretized → returns None
  assert _subdir(['a', '..', '..'], ['b']) is None

def test_subdir_internal_nonconcretizable_path():
  # path cannot be concretized → returns None
  assert _subdir(['a'], ['a', '..', '..']) is None

#===============================================================================
# path/utils.py — subdir (public)
#===============================================================================
def test_subdir_raises_when_not_subdir():
  with raises(PathError):
    subdir(PurePath('a/b'), PurePath('c/d'))

def test_subdir_returns_none_when_check_false():
  assert subdir(PurePath('a/b'), PurePath('c/d'), check=False) is None

def test_subdir_ok():
  assert subdir(PurePath('a'), PurePath('a/b/c')) == PurePath('b/c')

#===============================================================================
# path/utils.py — file_size_mtime
#===============================================================================
def test_file_size_mtime_missing(tmp_path):
  missing = tmp_path / 'does_not_exist.txt'
  mtime, size, path = file_size_mtime(str(missing))
  assert mtime == 0
  assert size == 0
  assert path == str(missing)

def test_file_size_mtime_existing(tmp_path):
  f = tmp_path / 'real.txt'
  f.write_bytes(b'hello')
  mtime, size, path = file_size_mtime(str(f))
  assert size == 5
  assert mtime > 0

#===============================================================================
# path/utils.py — git_tracked_mtime
#===============================================================================
def test_git_tracked_mtime():
  commit, files = git_tracked_mtime()
  assert isinstance(commit, str) and len(commit) > 0
  assert isinstance(files, list)
  assert all(isinstance(t, tuple) and len(t) == 3 for t in files)

def test_git_tracked_mtime_with_root():
  commit1, files1 = git_tracked_mtime()
  commit2, files2 = git_tracked_mtime(root=Path('.'))
  assert commit1 == commit2
  assert len(files1) == len(files2)

#===============================================================================
# path/match.py — PathMatcher edge cases
#===============================================================================
def test_matcher_start_as_string():
  m = PathMatcher('bar', start='src')
  assert m.start == PurePath('src')

def test_matcher_repr():
  # bare pattern
  r = repr(PathMatcher('foo'))
  assert 'foo' in r
  # negate flag
  r = repr(PathMatcher('!foo'))
  assert 'negate' in r
  # dironly + start (covers start branch and relative branch in repr)
  r = repr(PathMatcher('a/b/', start=PurePath('root')))
  assert 'dironly' in r
  assert 'start' in r

def test_matcher_match_none():
  assert PathMatcher('foo').match(None) is False

def test_matcher_match_string_path():
  assert PathMatcher('foo').match('foo')
  assert not PathMatcher('foo').match('bar')

def test_matcher_match_with_start():
  m = PathMatcher('bar', start=PurePath('src'))
  # path under start → matches
  assert m.match(PurePath('src/bar'))
  # path not under start → does not match (returns False explicitly)
  assert m.match(PurePath('other/bar')) is False

def test_matcher_nt():
  m = PathMatcher('foo/bar')
  assert m.nt('foo\\bar')
  assert not m.nt('baz\\bar')

#===============================================================================
# path/match.py — PathFilter edge cases
#===============================================================================
def test_filter_init_single_string():
  pf = PathFilter('*.py')
  assert len(pf.patterns) == 1
  assert pf.patterns[0].posix('mod.py')

def test_filter_init_single_matcher():
  inner = PathMatcher('*.py')
  pf = PathFilter(inner)
  assert len(pf.patterns) == 1
  assert pf.patterns[0] is inner

def test_filter_init_start_as_string():
  pf = PathFilter(['*.py'], start='src')
  assert pf.start == PurePath('src')

def test_filter_dnames_none():
  # when dnames is omitted, entries ending with osp.sep are treated as dirs
  pf = PathFilter(['a/'])  # dironly pattern
  result = pf.filter('.', fnames=['a' + osp.sep, 'b.py'])
  assert result == {'a'}

def test_filter_pattern_with_start():
  # PathMatcher inside the filter has its own start — hits line 332 of match.py
  inner = PathMatcher('bar', start=PurePath('src'), relative=True)
  pf = PathFilter([inner])
  # 'bar' inside 'src' matches
  assert pf.filter(PurePath('src'), fnames=['bar']) == {'bar'}
  # 'bar' inside 'other' does not match; check=False avoids PathPatternError
  # since 'other' is not under the pattern's start ('src')
  assert pf.filter(PurePath('other'), fnames=['bar'], check=False) == set()

def test_filter_repr():
  r = repr(PathFilter(['*.py'], start=PurePath('src')))
  assert 'PathFilter' in r

#===============================================================================
# path/match.py — contains
#===============================================================================
def test_contains():
  assert contains(PurePath('a/b'), PurePath('a/b/c')) is True
  assert contains(PurePath('a/b'), PurePath('a/b')) is True
  assert contains(PurePath('a/b'), PurePath('x/y')) is False

#===============================================================================
if __name__ == '__main__':
  test_match_any()
