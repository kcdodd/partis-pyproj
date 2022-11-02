import os
import os.path as osp
import glob
import pathlib
from pathlib import Path
from pathlib import PurePath
from pathlib import PurePosixPath

import logging

from ..validate import (
  ValidationError,
  FileOutsideRootError,
  validating )

from ..norms import (
  norm_path )

from ..path import (
  PathMatcher,
  PathFilter,
  combine_ignore_patterns,
  contains )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_iter(*,
  include,
  ignore,
  root ):

  patterns = PathFilter(
    patterns = ignore )

  for i, incl in enumerate(include):
    src = incl.src
    dst = incl.dst
    _ignore = incl.ignore

    _ignore_patterns = combine_ignore_patterns(
      patterns,
      PathFilter(
        patterns = _ignore,
        start = pathlib.PurePath(src) ) )

    if incl.glob:

      cwd = Path.cwd()
      try:
        os.chdir(src) #Doesn't seems to be an pathlib way of changing working direcotry
        matches = glob.glob(incl.glob, recursive = True)
      finally:
        os.chdir(cwd)

      for match in matches:
        _src = Pure(src).joinpath(match)
        # re-base the dst path, path relative to src == path relative to dst
        _dst = Pure(dst).joinpath(match)

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

        src = Path(src).resolve() #normpath is not something in pathlib, supposed to be a black box
        dst = '/'.join( [base_path, norm_path(dst)] )

        if not individual and ignore_patterns( PurePosixPath(src).parent, PurePosixPath(src).name):
          logger.debug( f'ignoring: {src}' )
          continue

        src_abs = Path(src).resolve()

        if root and not contains(root, src_abs):
          raise FileOutsideRootError(
            f"Must have common path with root:\n  file = \"{src_abs}\"\n  root = \"{root}\"")

        logger.debug(f"dist copy: {src} -> {dst}")

        if Path.is_dir(src):
          dist.copytree(
            src = src,
            dst = dst,
            ignore = ignore_patterns )

        else:
          dist.copyfile(
            src = src,
            dst = dst )
