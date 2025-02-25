from __future__ import annotations
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
    tmp_file = cache_file.with_name(cache_file.name+'.tmp')

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

      with requests.get(url, stream=True) as req, tmp_file.open('wb') as fp:
        for chunk in req.iter_content(chunk_size=chunk_size):
          if chunk:
            fp.write(chunk)
            size += len(chunk)

            if hash:
              hash.update(chunk)

            if size - last_size > 50e6:
              logger.info(f"- {size/1e6:,.1f} MB")
              last_size = size

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
    logger.info(f"- extracting: {cache_file} -> {build_dir}")
    with tarfile.open(cache_file, 'r:*') as fp:
      fp.extractall(
        path=build_dir,
        members=None,
        numeric_owner=False,
        filter='tar')

  if executable:
    logger.info("- setting executable permission")
    out_file.chmod(out_file.stat().st_mode|stat.S_IXUSR)

#===============================================================================
def _cached_download(url: str, checksum: str) -> Path:
  if not checksum:
    checksum = '0'

  cache_dir = Path(tempfile.gettempdir())/'partis-pyproj-downloads'
  name = url.split('/')[-1]
  _url = url

  if name != _url:
    _url = _url.removesuffix('/'+name)

  url_dir = cache_dir/_filename_subs.sub('_', _url)
  url_filename = _filename_subs.sub('_', name)

  url_dir.mkdir(exist_ok=True, parents=True)
  file = url_dir/url_filename
  info_file = file.with_name(file.name+'.info')
  info_file.write_text(f"{url}\n{checksum}")
  return file
