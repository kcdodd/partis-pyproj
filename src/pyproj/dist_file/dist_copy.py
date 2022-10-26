import os
import os.path as osp
import glob
import pathlib
import logging

from ..validate import (
  ValidationError,
  FileOutsideRootError,
  validating )

from ..norms import (
  norm_path )

from ..path import (
  FilePattern,
  FilePatterns,
  combine_ignore_patterns,
  contains )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_iter(*,
  include,
  ignore,
  root ):

  patterns = FilePatterns(
    patterns = ignore )

  for i, incl in enumerate(include):
    src = incl.src
    dst = incl.dst
    _ignore = incl.ignore

    _ignore_patterns = combine_ignore_patterns(
      patterns,
      FilePatterns(
        patterns = _ignore,
        start = pathlib.PurePath(src) ) )

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

        if not individual and ignore_patterns( osp.dirname(src), [osp.basename(src)]):
          logger.debug( f'ignoring: {src}' )
          continue

        src_abs = osp.realpath(src)

        if root and not contains(root, src_abs):
          raise FileOutsideRootError(
            f"Must have common path with root:\n  file = \"{src_abs}\"\n  root = \"{root}\"")

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
