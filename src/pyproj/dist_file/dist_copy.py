from __future__ import annotations
import os
import glob
from pathlib import (
  Path)
import logging
from ..validate import (
  FileOutsideRootError,
  validating )
from ..path import (
  PathFilter,
  subdir,
  combine_ignore_patterns,
  resolve)

# #===============================================================================
# def rematch_replace(rematch, replace, name):

#   m = rematch.fullmatch(path)
#   if not m:
#     continue

#   args = (m.group(0), *m.groups())
#   kwargs = m.groupdict()
#   try:
#     replace.format(*args, **kwargs))
#   except (IndexError, KeyError) as e:
#     raise ValueError(
#       f"Replacement '{replace}' failed to format match '{m.group(0)}': "
#       f"{args}, {kwargs}") from None



#===============================================================================
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
        start = src ) )

    if not incl.include:
      yield ( i, src, dst, _ignore_patterns, True )
    else:
      for incl_pattern in incl.include:
        cwd = Path.cwd()
        try:
          # TODO: better way of globing *relative* to src directory
          os.chdir(src)
          matches = glob.glob(incl_pattern.glob, recursive = True)
        finally:
          os.chdir(cwd)

        for match in matches:
          match = Path(match)
          basename = match.parent
          src_filename = match.name

          m = incl_pattern.rematch.fullmatch(src_filename)
          if not m:
            continue

          args = (m.group(0), *m.groups())
          kwargs = m.groupdict()
          try:
            dst_filename = incl_pattern.replace.format(*args, **kwargs)
          except (IndexError, KeyError) as e:
            raise ValueError(
              f"Replacement '{incl_pattern.replace}' failed for"
              f" '{incl_pattern.rematch.pattern}':"
              f" {args}, {kwargs}") from None

          _src = src/basename/src_filename
          # re-base the dst path, path relative to src == path relative to dst
          _dst = dst/basename/dst_filename

          yield (i, _src, _dst, _ignore_patterns, False)


#===============================================================================
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

        dst = base_path.joinpath(dst)

        if not individual and ignore_patterns( src.parent, [src.name]):
          logger.debug( f'ignoring: {src}' )
          continue

        src_abs = resolve(src)

        if root and not subdir(root, src_abs, check = False):
          raise FileOutsideRootError(
            f"Must have common path with root:\n  file = \"{src_abs}\"\n  root = \"{root}\"")

        logger.debug(f"dist copy: {src} -> {dst}")

        if src.is_dir():
          dist.copytree(
            src = src,
            dst = dst,
            ignore = ignore_patterns )

        else:
          dist.copyfile(
            src = src,
            dst = dst )
