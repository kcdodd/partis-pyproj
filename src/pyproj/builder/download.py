from __future__ import annotations
import sys
import os
import platform
import stat
import re
from pathlib import Path
import hashlib
from urllib.parse import urlsplit
import tarfile
import tempfile
from base64 import urlsafe_b64encode
import logging
from .builder import (
  ProcessRunner)
from ..validate import (
  ValidationError)
from ..norms import b64_nopad, nonempty_str
from ..cache import cache_dir

# replace runs of non-alphanumeric, dot, dash, or underscore
_filename_subs = re.compile(r'[^a-z0-9\.\-\_]+', re.I)

#===============================================================================
def download(
  pyproj,
  logger: logging.Logger,
  options: dict,
  work_dir: Path,
  src_dir: Path,
  build_dir: Path,
  prefix: Path,
  setup_args: list[str],
  compile_args: list[str],
  install_args: list[str],
  build_clean: bool,
  runner: ProcessRunner):
  """Download a file
  """
  import requests

  chunk_size = int(options.get('chunk_size', 2**16))

  url = options.get('url')
  executable = options.get('executable')

  if not url:
    raise ValidationError(
      "Download 'url' required")

  url = nonempty_str(url)

  checksum = options.get('checksum')

  if checksum is None:
    raise ValidationError(
      "Download 'checksum' required, or explicitly set 'checksum=false'")


  filename = options.get('filename', url.split('/')[-1])
  extract = options.get('extract', None)

  cache_file = _cached_download(url, checksum)
  out_file = build_dir/filename

  if cache_file.exists():
    logger.info(f"Using cache file: {cache_file}")

  else:
    # name unique to host/process as countermeasure for race condition
    hostname = re.sub(r'[^a-zA-Z0-9]+', '_', str(platform.node()))
    tmp_name = f"{cache_file.name}-{hostname}-{os.getpid():06d}.tmp"
    tmp_file = cache_file.with_name(tmp_name)

    if tmp_file.exists():
      tmp_file.unlink()

    if checksum:
      checksum = checksum.lower()
      alg, _, checksum = checksum.partition('=')

      try:
        hash = getattr(hashlib, alg)()

      except AttributeError:
        raise ValidationError(
          f"Checksum algorithm must be one of {hashlib.algorithms_available}: got {alg}") from None

    else:
      hash = None

    size = 0
    last_size = 0

    try:
      logger.info(f"- downloading: {url} -> {tmp_file}")

      req = requests.get(url, stream=True)

      if not req.ok:
        req.raise_for_status()

      with req, tmp_file.open('wb') as fp:
        for chunk in req.iter_content(chunk_size=chunk_size):
          if chunk:
            fp.write(chunk)
            size += len(chunk)

            if hash:
              hash.update(chunk)

            if size - last_size > 50e6:
              logger.info(f"- {size/1e6:,.1f} MB")
              last_size = size

      if size == 0:
        raise ValidationError(f"Downloaded file had zero size: {url}")

      logger.info(f"- complete {size/1e6:,.1f} MB")

      if hash:
        digest = hash.digest()

        if checksum.endswith('='):
          digest = urlsafe_b64encode(digest).decode("ascii")
        elif checksum.startswith('x'):
          digest = 'x'+digest.hex()
        else:
          digest = digest.hex()

        checksum_ok = checksum == digest
        logger.info(f"- checksum{' (OK)' if checksum_ok else ''}: {alg}={digest}")

        if not checksum_ok:
          raise ValidationError(f"Download checksum did not match: {digest} != {checksum}")

    except Exception:
      if tmp_file.exists():
        tmp_file.unlink()

      raise

    tmp_file.replace(cache_file)


  out_file.symlink_to(cache_file)

  if extract:
    out_dir = build_dir

    if isinstance(extract, (str,Path)):
      out_dir = extract

    logger.info(f"- extracting: {cache_file} -> {out_dir}")

    with tarfile.open(cache_file, 'r:*') as fp:
      if sys.version_info >= (3, 12):
        # 'filter' argument added, controls behavior of extract
        fp.extractall(
          path=out_dir,
          members=None,
          numeric_owner=False,
          filter='tar')
      else:
        fp.extractall(
          path=out_dir,
          members=None,
          numeric_owner=False)

  if executable:
    logger.info("- setting executable permission")
    out_file.chmod(out_file.stat().st_mode|stat.S_IXUSR)

#===============================================================================
def _cached_download(url: str, checksum: str) -> Path:
  if not checksum:
    checksum = '0'

  name = url.split('/')[-1]
  _url = url

  # hash of url + checksum used to prevent filename collision after url is sanitized
  h = hashlib.sha256()
  h.update(url.encode('utf-8') + checksum.encode('utf-8'))
  # keep only 4 bytes (8 hex characters) worth of the hash
  short = h.digest()[:4].hex()

  if name != _url:
    # possible for url without a path segment?
    _url = _url.removesuffix('/'+name)

  url_dirname = _filename_subs.sub('_', _url)
  url_filename = f"{short}-" + _filename_subs.sub('_', name)

  url_dir = cache_dir()/'download'/url_dirname
  url_dir.mkdir(exist_ok=True, parents=True)

  file = url_dir/url_filename

  info_file = file.with_name(file.name+'.info')
  info_file.write_text(f"{url}\n{checksum}")

  return file
