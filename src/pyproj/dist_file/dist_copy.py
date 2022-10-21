import os
import os.path as osp
import glob
import logging
import re
from fnmatch import (
  translate )
import posixpath

from ..validate import (
  ValidationError,
  FileOutsideRootError,
  validating )

from ..norms import (
  norm_path )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def norm_join_base(base, dirname, names):
  """Creates paths relative to a 'base' path for a list of names in a 'dirname'
  """

  rpath = osp.normcase( osp.relpath( dirname, start = base ) )

  if osp is posixpath:
    return [
      (name, osp.normpath( osp.join(rpath, name) ))
      for name in names ]
  else:
    return [
      (name, osp.normpath( osp.join(rpath, osp.normcase(name)) ))
      for name in names ]

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def combine_ignore_patterns(*ignores):

  def _ignore_patterns(path, names):
    ignored_names = DiffSet()

    for ignore in ignores:
      ignored_names |= ignore(path, names)

    return ignored_names

  return _ignore_patterns

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_iter(*,
  include,
  ignore,
  root ):

  ignore_patterns = FilePatterns(
    patterns = ignore,
    start = '.',
    root = root )

  for i, incl in enumerate(include):
    src = incl.src
    dst = incl.dst
    _ignore = incl.ignore

    _ignore_patterns = combine_ignore_patterns(
      ignore_patterns,
      FilePatterns(
        patterns = _ignore,
        start = src,
        root = root ) )

    if incl.glob:

      cwd = os.getcwd()
      try:
        os.chdir(src)
        matches = glob.glob(incl.glob, recursive = True)
      finally:
        os.chdir(cwd)

      for match in matches:
        _src = osp.join(src, match)
        # re-base the dst path, path relative to src == path relative to dst
        _dst = osp.join(dst, match)

        yield ( i, _src, _dst, _ignore_patterns, False )

    else:

      yield ( i, src, dst, _ignore_patterns, True )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_copy(*,
  base_path,
  include,
  ignore,
  dist,
  root = None,
  logger = None ):

  if len(include) == 0:
    return

  logger = logger or logging.getLogger( __name__ )

  with validating(key = 'copy'):

    for i, src, dst, ignore_patterns, individual in dist_iter(
      include = include,
      ignore = ignore,
      root = root ):

      with validating(key = i):

        src = osp.normpath( src )
        dst = '/'.join( [base_path, norm_path(dst)] )

        ignored = ignore_patterns(
          osp.dirname(src),
          [ osp.basename(src) ])

        if ignored and not individual:
          logger.debug( f'ignoring: {src}' )
          continue

        logger.debug(f"dist copy: {src} -> {dst}")

        if osp.isdir( src ):
          dist.copytree(
            src = src,
            dst = dst,
            ignore = ignore_patterns )

        else:
          dist.copyfile(
            src = src,
            dst = dst )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class DiffSet(set):
  #-----------------------------------------------------------------------------
  def __init__(self, nominal = None, complement = None):
    if isinstance(complement, bool):
      if complement:
        complement = nominal
        nominal = None
      else:
        complement = None

    if nominal is None:
      nominal = set()
    else:
      nominal = set(nominal)

    if complement is None:
      complement = set()
    else:
      complement = set(complement)

    self.nominal = nominal
    self.complement = complement

    super().__init__(nominal - complement)

  #-----------------------------------------------------------------------------
  def __or__(self, other):
    nominal = self.nominal
    complement = self.complement

    if isinstance(other, DiffSet):
      nominal |= other.nominal
      complement |= other.complement
    else:
      nominal |= other

    return DiffSet(nominal, complement)

  #-----------------------------------------------------------------------------
  def __str__(self):
    return f"{self.nominal} - {self.complement}" if self.complement else str(self.nominal)

  #-----------------------------------------------------------------------------
  def __and__(self, other):
    nominal = self.nominal
    complement = self.complement

    if isinstance(other, DiffSet):
      nominal &= other.nominal
      # NOTE: complement of set does not decrease
      complement |= other.complement
    else:
      nominal &= other

    return DiffSet(nominal, complement)

  #-----------------------------------------------------------------------------
  def __sub__(self, other):
    nominal = self.nominal
    complement = self.complement

    if isinstance(other, DiffSet):
      nominal -= other.nominal
      # NOTE: complement of set does not decrease
      complement |= other.complement
    else:
      nominal -= other

    return DiffSet(nominal, complement)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class CompSet(DiffSet):
  #-----------------------------------------------------------------------------
  def __init__(self, complement = None, nominal = None):
    super().__init__(nominal, complement)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FilePattern:
  #-----------------------------------------------------------------------------
  def __init__(self, pattern):
    pattern = pattern.strip()
    _pattern = pattern
    negate = False
    dironly = False
    relative = False

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

    if pattern.count('/') > int(dironly):
      # If there is a separator at the beginning or middle (or both) of the
      # pattern, then the pattern is relative to the directory level of the
      # particular .gitignore file itself.
      relative = True

    self._pattern = _pattern
    self.pattern = re.compile( translate( osp.normcase(pattern) ) )
    self.match = self.pattern.match
    self.negate = negate
    self.dironly = dironly
    self.relative = relative

  #-----------------------------------------------------------------------------
  def __str__(self):
    return self._pattern

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class FilePatterns:
  #-----------------------------------------------------------------------------
  def __init__(self, patterns, start = None, root = None):
    self.patterns = [
      p if isinstance(p, FilePattern) else FilePattern(p)
      for p in patterns ]

    if start is not None:
      start = osp.normcase(osp.normpath(os.fspath(start)))

    if root is not None:
      root = osp.normcase(osp.normpath(os.fspath(root)))

    self.start = start
    self.root = root

  #-----------------------------------------------------------------------------
  def __call__(self, dir, names):
    dir = osp.normcase(osp.normpath(os.fspath(dir)))
    name_paths = norm_join_base(self.start, dir, names)

    # print(f"{dir}")

    # Can only match directories, filter out other names
    dir_name_paths = [
      (name, path)
      for name, path in name_paths
      if osp.isdir(osp.join(dir, name)) ]

    match_set = DiffSet()

    for pattern in self.patterns:
      set_type = CompSet if pattern.negate else DiffSet
      _name_paths = dir_name_paths if pattern.dironly else name_paths
      match = pattern.match

      if pattern.relative:
        _match_set = set_type([ name for name, path in _name_paths if match(path) ])
      else:
        _match_set = set_type([ name for name, path in _name_paths if match(name) ])

      # print(f"  {pattern}: {_match_set}")

      match_set |= _match_set

    if self.root:
      for name in names:
        if name not in match_set:
          abs_path = osp.realpath( osp.join(dir, name) )
          prefix = osp.commonpath([self.root, abs_path])

          if prefix != self.root:
            raise FileOutsideRootError(
              f"Must have common path with root:\n  file = \"{abs_path}\"\n  root = \"{self.root}\"")

    return match_set
