from __future__ import annotations
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

  if url is None:
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

  if not cache_file.exists():
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

    try:
      with requests.get(url, stream=True) as req, tmp_file.open('wb') as fp:
        for chunk in req.iter_content(chunk_size=chunk_size):
          if chunk:
            fp.write(chunk)
            size += len(chunk)

            if hash:
              hash.update(chunk)

      if hash:
        digest = hash.digest()

        if checksum.endswith('='):
          digest = urlsafe_b64encode(digest).decode("ascii")
        elif checksum.startswith('x'):
          digest = 'x'+digest.hex()
        else:
          digest = digest.hex()


        if checksum != digest:
          raise ValidationError(f"Download checksum did not match: {digest} != {checksum}")

    except Exception:
      if tmp_file.exists():
        tmp_file.unlink()

      raise

    tmp_file.replace(cache_file)


  out_file.symlink_to(cache_file)

  if extract:
    with tarfile.open(cache_file, 'r:*') as fp:
      fp.extractall(
        path=build_dir,
        members=None,
        numeric_owner=False,
        filter='tar')

#===============================================================================
def _cached_download(url: str, checksum: str) -> Path:
  if not checksum:
    checksum = '0'

  cache_dir = Path(tempfile.gettempdir())/'partis-pyproj-downloads'
  url_dir = cache_dir/b64_nopad(url.encode('utf-8'))
  url_dir.mkdir(exist_ok=True, parents=True)
  file = url_dir/b64_nopad(checksum.encode('utf-8'))
  info_file = file.with_name(file.name+'.info')
  info_file.write_text(f"{url}\n{checksum}")
  return file
