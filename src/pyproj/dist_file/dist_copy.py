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
def compile_patterns(base, patterns):
  """Creates compiled glob patterns
  """
  patterns = [ osp.normcase(p) for p in patterns ]

  # create mask for patterns containing path separator
  # these are clearly intended to be matched against the full path name of the file.
  base_mask = [ p.find(osp.sep) >= 0 for p in patterns ]

  return base_mask, [
    re.compile( translate(p) ).match
    for p in patterns ]

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def match_names(name_paths, base_mask, pattern_matches):
  """Matches filenames base on either the basename, or path relative to base path,
  depending on if the compiled pattern was detected to be for a single name or
  a path
  """

  filtered_names = []

  for mask, match in zip(base_mask, pattern_matches):
    if mask:
      filtered_names.extend([ name for name, path in name_paths if match(path) ])
    else:
      filtered_names.extend([ name for name, path in name_paths if match(name) ])

  return filtered_names

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def root_ignore_patterns(
  *patterns,
  base,
  root ):
  """Create ignore function that checks for files that don't have common path with root

  Parameters
  ----------
  *patterns : str
    Patterns used to match ignore files using :mod:`fnmatch `
  base : str
    Base path used for path-like ignore patterns (those containing a path separator)
  root : str
    Base path to check real paths against. Any files found that do not have a common
    path with root, and which would not otherwise be ignored,
    will raise an ``FileOutsideRootError``.

  Raises
  ------
  FileOutsideRootError

  See Also
  --------
  * :func:`shutil.ignore_patterns` : This factory function creates a function
    that can be used as a callable for copytree()'s ignore argument, ignoring
    files and directories that match one of the glob-style patterns provided.

  """

  base = osp.normpath(os.fspath(base))
  root = osp.normpath(os.fspath(root))

  base_mask, pattern_matches = compile_patterns(base, patterns)

  def _ignore_patterns(path, names):
    path = osp.normpath(os.fspath(path))

    name_paths = norm_join_base( base, path, names )
    ignored_names = match_names(name_paths, base_mask, pattern_matches)

    # debugging prints (no logging)
    # print('base: ', base)
    # print('patterns: ', list(zip(base_mask,patterns)))
    # print('name_paths: ', name_paths)
    # print('ignored_names: ', ignored_names)

    for name in names:
      if name not in ignored_names:
        abs_path = osp.realpath( osp.join(
          path,
          name ) )

        prefix = osp.commonpath([root, abs_path])

        if prefix != root:
          raise FileOutsideRootError(
            f"Must have common path with root:\n  file = \"{abs_path}\"\n  root = \"{root}\"")

    return set(ignored_names)

  return _ignore_patterns

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def combine_ignore_patterns(*ignores):

  def _ignore_patterns(path, names):
    ignored_names = set()

    for ignore in ignores:
      ignored_names |= ignore(path, names)

    return ignored_names

  return _ignore_patterns

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_iter(*,
  include,
  ignore,
  root ):

  ignore_patterns = root_ignore_patterns(
    *ignore,
    base = '.',
    root = root )

  for i, incl in enumerate(include):
    src = incl.src
    dst = incl.dst
    _ignore = incl.ignore

    _ignore_patterns = combine_ignore_patterns(
      ignore_patterns,
      root_ignore_patterns(
        *_ignore,
        base = src,
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
