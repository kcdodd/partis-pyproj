from __future__ import annotations
import os
import glob
from pathlib import (
  Path)
import logging
from ..validate import (
  FileOutsideRootError,
  ValidationError,
  validating )
from ..path import (
  PathFilter,
  subdir,
  combine_ignore_patterns,
  resolve)
from ..pptoml import (
  pyproj_dist_copy)

#===============================================================================
def _rglob(pattern: str, *, root_dir: Path) -> list[Path]:
  # detect if glob will be recursive by finding '**' in the pattern
  recursive = '**' in pattern

  # NOTE: root_dir added in Python 3.10
  cwd = Path.cwd()

  try:
    os.chdir(root_dir)
    matches = glob.glob(pattern, recursive = recursive)

    matches = [Path(m) for m in matches]

    if recursive:
      # don't match directories in recursive mode, since copying a parent
      # directory negates the need to recurse
      matches = [m for m in matches if not m.is_dir()]

  finally:
    os.chdir(cwd)

  return matches

#===============================================================================
def dist_iter(*,
  copy_items: list[pyproj_dist_copy],
  ignore: list[str],
  root: Path,
  logger: logging.Logger):

  patterns  = PathFilter(
    patterns = ignore )



  for i, incl in enumerate(copy_items):
    src = incl.src
    dst = incl.dst
    _ignore = incl.ignore

    _ignore_patterns = combine_ignore_patterns(
      patterns,
      PathFilter(
        patterns = _ignore,
        start = src ) )

    if not incl.include:
      # each copy specifies a single path
      # logger.debug(f"  - from: {src}\n  -   to: {dst}")
      yield ( i, src, dst, _ignore_patterns, True )

    else:
      # each copy can result in many paths
      for incl_pattern in incl.include:
        # produce list of possible copies by glob pattern, relative to 'src'
        matches = _rglob(incl_pattern.glob, root_dir=src)
        # logger.debug(f"- glob: {len(matches)} matches with pattern {incl_pattern.glob!r} in {str(src)!r}")

        if not matches:
          logger.warning(f"Copy pattern did not yield any files: {incl_pattern.glob!r}")
          continue

        for i, match in enumerate(matches):
          parent = match.parent
          src_filename = match.name

          if _ignore_patterns(src/parent, [src_filename]):
            # Only filter by ignore pattern if this path was part of a glob
            # logger.debug(f"  - ignored: {match}")
            continue

          # logger.debug(f"  - match: {match}")

          if incl_pattern.strip:
            # remove leading path components
            dst_parent = type(parent)(*parent.parts[incl_pattern.strip:])
            # logger.debug(f"    - stripped:  {parent.parts[:incl_pattern.strip]}")
          else:
            dst_parent = parent

          # match to regular expression
          m = incl_pattern.rematch.fullmatch(src_filename)

          if not m:
            # logger.debug(f"    - !rematch: {src_filename!r} (pattern = {incl_pattern.rematch})")
            continue

          # apply replacement
          if incl_pattern.replace == '{0}':
            dst_filename = src_filename

          else:
            args = (m.group(0), *m.groups())
            kwargs = m.groupdict()

            try:
              dst_filename = incl_pattern.replace.format(*args, **kwargs)
              # logger.debug(f"    - renamed: {dst_filename!r} (template = {incl_pattern.replace!r})")

            except (IndexError, KeyError) as e:
              raise ValidationError(
                f"Replacement '{incl_pattern.replace}' failed for"
                f" '{incl_pattern.rematch.pattern}':"
                f" {args}, {kwargs}") from None

          _src = src/parent/src_filename
          # re-base the dst path, (path relative to src) == (path relative to dst)
          _dst = dst/dst_parent/dst_filename

          # logger.debug(f"    - from: {str(_src)!r}\n    -   to: {str(_dst)!r}")

          yield (i, _src, _dst, _ignore_patterns, False)


#===============================================================================
def dist_copy(*,
  base_path: Path,
  copy_items: list[pyproj_dist_copy],
  ignore,
  dist,
  root = None,
  logger = None ):

  if len(copy_items) == 0:
    return

  logger = logger or logging.getLogger( __name__ )
  # logger.debug(f"copy items = {copy_items}, ignore = {ignore}")

  copy_history: set[tuple[Path, Path]] = set()
  num_copies = len(copy_history)

  with validating(key = 'copy'):

    for i, src, dst, ignore_patterns, individual in dist_iter(
      copy_items = copy_items,
      ignore = ignore,
      root = root,
      logger = logger):

      with validating(key = i):

        dst = base_path.joinpath(dst)
        src_abs = resolve(src)

        if root and not subdir(root, src_abs, check = False):
          # TODO: specialize error message for symlinks?
          raise FileOutsideRootError(
            f"Must have common path with root:\n  file = \"{src_abs}\"\n  root = \"{root}\"")

        copy_history.add((src, dst))

        if len(copy_history) == num_copies:
          # ignore exactly duplicate copy operations
          continue

        num_copies = len(copy_history)

        if src.is_symlink():
          target = Path(os.readlink(src))

          # if not target.is_absolute():
          #   # ensure minimal path within distribution
          #   target = resolve(src/target)

          # target = target.relative_to(src)

          dist.write_link(dst, target, mode = src.stat().st_mode)

        elif src.is_dir():
          dist.copytree(
            src = src,
            dst = dst,
            ignore = ignore_patterns )

        else:
          dist.copyfile(
            src = src,
            dst = dst,
            mode = src.stat().st_mode)
