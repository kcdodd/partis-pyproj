from __future__ import annotations
import os
from collections.abc import Iterable
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
  resolve,
  FileInfo,
  DirInfo,
  scandir_recursive)
from ..pptoml import (
  Include,
  PyprojDistCopy)

#===============================================================================
def dist_iter(*,
  copy_items: list[PyprojDistCopy],
  ignore: list[str],
  root: Path,
  logger: logging.Logger,
  follow_symlinks: bool = False):

  exclude = (PathFilter(ignore),)

  # pre-scan all files in the project
  scanned: DirInfo = scandir_recursive(root, follow_symlinks=follow_symlinks)

  for i, cp in enumerate(copy_items):
    src = cp.src
    dst = cp.dst
    include = cp.include

    # logger.debug(f"  - copy: {src} >> {dst}")

    if _ignore := cp.ignore:
      # logger.debug(f"    - ignore: {cp.ignore}")
      _exclude = exclude + (PathFilter(_ignore, start = src),)
    else:
      _exclude = exclude

    try:
      src_info = scanned.get(src)
    except Exception as e:
      # raise ValidationError() from e
      logger.error(f"    - error: {e}", exc_info=e)
      raise

    # logger.debug(f"    - src_info: {src_info}")

    if type(src_info) is FileInfo:
      # logger.debug(f"    - from: {str(src)!r}")
      # logger.debug(f"    -   to: {str(dst)!r}")
      yield (i, src, dst)
      continue

    if not include:
      include = [Include()]

    for incl in include:
      try:
        matches = src_info.glob(
          PathFilter(incl.glob, start=src),
          exclude = _exclude,
          dirpath = src)
      except Exception as e:
        logger.error(f"    - error: {e}", exc_info=e)
        raise

      # logger.debug(f"    - glob: {incl.glob} -> {len(matches)} matches")

      if not matches:
        logger.warning(f"Copy pattern did not yield any files: {incl.glob!r}")
        continue

      for i, (path, info) in enumerate(matches):
        parent = path.parent.relative_to(src)
        src_filename = path.name
        # logger.debug(f"    - match:  {parent/src_filename}")

        if incl.strip:
          # remove leading path components
          dst_parent = type(parent)(*parent.parts[incl.strip:])
          # logger.debug(f"      - stripped:  {parent.parts[:incl.strip]}")
        else:
          dst_parent = parent

        # match to regular expression
        m = incl.rematch.fullmatch(src_filename)

        if not m:
          # logger.debug(f"      - !rematch: {src_filename!r} (pattern = {incl.rematch})")
          continue

        # apply replacement
        if incl.replace == '{0}':
          dst_filename = src_filename

        else:
          args = (m.group(0), *m.groups())
          kwargs = m.groupdict()

          try:
            dst_filename = incl.replace.format(*args, **kwargs)
            # logger.debug(f"      - renamed: {src_filename!r} -> {dst_filename!r} ({incl.rematch.pattern!r} -> {incl.replace!r})")

          except (IndexError, KeyError) as e:
            raise ValidationError(
              f"Replacement {incl.replace!r} failed for"
              f" {incl.rematch.pattern!r}:"
              f" {args}, {kwargs}") from None

        _src = src/parent/src_filename
        # re-base the dst path, (path relative to src) == (path relative to dst)
        _dst = dst/dst_parent/dst_filename

        # logger.debug(f"      - from: {str(_src)!r}")
        # logger.debug(f"      -   to: {str(_dst)!r}")
        yield (i, _src, _dst)

#===============================================================================
def dist_copy(*,
  base_path: Path,
  copy_items: list[PyprojDistCopy],
  ignore,
  dist,
  root = None,
  logger = None,
  follow_symlinks: bool = False):

  if len(copy_items) == 0:
    return

  logger = logger or logging.getLogger( __name__ )
  # logger.debug(f"copy items = {copy_items}, ignore = {ignore}")

  copy_history: set[tuple[Path, Path]] = set()
  num_copies = len(copy_history)

  with validating(key = 'copy'):

    for i, src, dst in dist_iter(
      copy_items = copy_items,
      ignore = ignore,
      root = root,
      follow_symlinks = follow_symlinks,
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

        if not follow_symlinks and src.is_symlink():
          target = Path(os.readlink(src))

          # if not target.is_absolute():
          #   # ensure minimal path within distribution
          #   target = resolve(src/target)

          # target = target.relative_to(src)

          dist.write_link(dst, target, mode = src.stat().st_mode)

        elif src.is_dir():
          raise AssertionError("dist_iter should not yield directories")

        else:
          dist.copyfile(
            src = src,
            dst = dst,
            mode = src.stat().st_mode)
