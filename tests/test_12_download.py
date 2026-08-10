import http.server
import socketserver
import threading
import tarfile
import tempfile
import hashlib
import logging
import os
import stat
from functools import partial
from pathlib import Path

import pytest

import importlib
download = importlib.import_module("partis.pyproj.builder.download")
from partis.pyproj.validate import ValidationError
from partis.pyproj import cache

class SilentHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def start_server(directory: Path):
    handler = partial(SilentHTTPRequestHandler, directory=str(directory))
    httpd = socketserver.TCPServer(("localhost", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()
    url = f"http://localhost:{httpd.server_address[1]}"
    return httpd, thread, url


def create_tar(directory: Path) -> tuple[Path, str]:
    inner = directory / "inner.txt"
    inner.write_text("data")
    tar_path = directory / "file.tar"
    with tarfile.open(tar_path, "w") as tf:
        tf.add(inner, arcname="inner.txt")
    digest = hashlib.sha256(tar_path.read_bytes()).hexdigest()
    return tar_path, digest


def test_cached_download_sanitizes_and_writes_info(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)

    url = "https://example.com/a b/c?d=e"
    checksum = "sha256=deadbeef"
    path = download._cached_download(url, checksum)
    # ensure filename sanitized
    assert " " not in str(path)
    info = path.with_name(path.name + ".info")
    assert info.read_text() == f"{url}\n{checksum}"


def test_download_extracts_and_sets_exec(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path/'cache')

    tar_path, digest = create_tar(tmp_path)
    httpd, thread, base = start_server(tmp_path)
    try:
        url = f"{base}/file.tar"
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        logger = logging.getLogger("test")
        opts = {
            "url": url,
            "checksum": f"sha256={digest}",
            "extract": True,
            "executable": True,
        }
        download.download(None, logger, opts, tmp_path, tmp_path, build_dir, tmp_path, [], [], [], False, runner=None)
        cache_file = download._cached_download(url, f"sha256={digest}")
        out_file = build_dir / "file.tar"
        assert out_file.is_symlink()
        assert out_file.resolve() == cache_file
        # extracted content
        assert (build_dir / "inner.txt").read_text() == "data"

        if os.name != 'nt':
          # not settable on windows
          # executable bit set
          assert out_file.stat().st_mode & stat.S_IXUSR

        # info file exists
        info = cache_file.with_name(cache_file.name + ".info")
        assert info.exists()
    finally:
        httpd.shutdown()
        thread.join()


def test_download_checksum_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path/'cache')

    tar_path, digest = create_tar(tmp_path)
    httpd, thread, base = start_server(tmp_path)
    try:
        url = f"{base}/file.tar"
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        logger = logging.getLogger("test")
        opts = {
            "url": url,
            "checksum": "sha256=" + "0" * 64,
        }
        with pytest.raises(ValidationError):
            download.download(None, logger, opts, tmp_path, tmp_path, build_dir, tmp_path, [], [], [], False, runner=None)
    finally:
        httpd.shutdown()
        thread.join()

#===============================================================================
# Validation errors that don't require network access
#===============================================================================

def test_download_missing_url(tmp_path):
  logger = logging.getLogger('test')
  with pytest.raises(ValidationError, match='url'):
    download.download(None, logger, {}, tmp_path, tmp_path, tmp_path, tmp_path, [], [], [], False, None)

def test_download_missing_checksum(tmp_path):
  logger = logging.getLogger('test')
  opts = {'url': 'http://example.com/file.tar'}
  with pytest.raises(ValidationError, match='checksum'):
    download.download(None, logger, opts, tmp_path, tmp_path, tmp_path, tmp_path, [], [], [], False, None)

def test_download_bad_algorithm(tmp_path, monkeypatch):
  monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / 'cache')
  logger = logging.getLogger('test')
  opts = {'url': 'http://example.com/file.tar', 'checksum': 'nosuchalg=abc123'}
  with pytest.raises(ValidationError, match='algorithm'):
    download.download(None, logger, opts, tmp_path, tmp_path, tmp_path, tmp_path, [], [], [], False, None)

#===============================================================================
# _cached_download — URL with no slash (name == _url branch, removesuffix skipped)
#===============================================================================

def test_cached_download_no_slash_url(tmp_path, monkeypatch):
  monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
  path = download._cached_download('myfile.tar.gz', 'sha256=abc')
  assert path.parent.is_dir()

#===============================================================================
# Zero-size download raises ValidationError
#===============================================================================

def test_download_zero_size(tmp_path, monkeypatch):
  monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / 'cache')
  (tmp_path / 'empty.bin').write_bytes(b'')
  httpd, thread, base = start_server(tmp_path)
  try:
    url = f"{base}/empty.bin"
    build_dir = tmp_path / 'build'
    build_dir.mkdir()
    logger = logging.getLogger('test')
    opts = {'url': url, 'checksum': 'sha256=abc123'}
    with pytest.raises(ValidationError, match='zero size'):
      download.download(None, logger, opts, tmp_path, tmp_path, build_dir, tmp_path, [], [], [], False, None)
  finally:
    httpd.shutdown()
    thread.join()

#===============================================================================
# checksum=False — skips hash verification (hash = None branch)
#===============================================================================

def test_download_no_checksum(tmp_path, monkeypatch):
  monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / 'cache')
  content = b'some binary content'
  (tmp_path / 'data.bin').write_bytes(content)
  httpd, thread, base = start_server(tmp_path)
  try:
    url = f"{base}/data.bin"
    build_dir = tmp_path / 'build'
    build_dir.mkdir()
    logger = logging.getLogger('test')
    opts = {'url': url, 'checksum': False}
    download.download(None, logger, opts, tmp_path, tmp_path, build_dir, tmp_path, [], [], [], False, None)
    assert (build_dir / 'data.bin').is_symlink()
  finally:
    httpd.shutdown()
    thread.join()

#===============================================================================
# Cache hit path (line 67) — second download reuses cached file
#===============================================================================

def test_download_cache_hit(tmp_path, monkeypatch):
  monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / 'cache')
  content = b'cached content'
  (tmp_path / 'cached.bin').write_bytes(content)
  httpd, thread, base = start_server(tmp_path)
  try:
    url = f"{base}/cached.bin"
    digest = hashlib.sha256(content).hexdigest()
    logger = logging.getLogger('test')
    opts = {'url': url, 'checksum': f"sha256={digest}"}

    build1 = tmp_path / 'build1'
    build1.mkdir()
    download.download(None, logger, opts, tmp_path, tmp_path, build1, tmp_path, [], [], [], False, None)

    # Second call: cache file exists → logger.info("Using cache file") branch
    build2 = tmp_path / 'build2'
    build2.mkdir()
    download.download(None, logger, opts, tmp_path, tmp_path, build2, tmp_path, [], [], [], False, None)
    assert (build2 / 'cached.bin').is_symlink()
  finally:
    httpd.shutdown()
    thread.join()

#===============================================================================
# HTTP error (lines 101, 138→141) — non-OK response raises, tmp_file never opened
#===============================================================================

def test_download_http_error(tmp_path, monkeypatch):
  monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / 'cache')
  httpd, thread, base = start_server(tmp_path)
  try:
    url = f"{base}/nonexistent_404.bin"
    build_dir = tmp_path / 'build'
    build_dir.mkdir()
    logger = logging.getLogger('test')
    opts = {'url': url, 'checksum': 'sha256=abc123'}
    with pytest.raises(Exception):  # requests.HTTPError
      download.download(None, logger, opts, tmp_path, tmp_path, build_dir, tmp_path, [], [], [], False, None)
  finally:
    httpd.shutdown()
    thread.join()

#===============================================================================
# Base64 checksum format (line 125) — checksum ending with '='
#===============================================================================

def test_download_checksum_base64(tmp_path, monkeypatch):
  from base64 import urlsafe_b64encode
  monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / 'cache')
  content = b'base64 test content'
  (tmp_path / 'b64.bin').write_bytes(content)
  digest_b64 = urlsafe_b64encode(hashlib.sha256(content).digest()).decode('ascii')
  httpd, thread, base = start_server(tmp_path)
  try:
    url = f"{base}/b64.bin"
    build_dir = tmp_path / 'build'
    build_dir.mkdir()
    logger = logging.getLogger('test')
    opts = {'url': url, 'checksum': f"sha256={digest_b64}"}  # ends with '='
    download.download(None, logger, opts, tmp_path, tmp_path, build_dir, tmp_path, [], [], [], False, None)
    assert (build_dir / 'b64.bin').is_symlink()
  finally:
    httpd.shutdown()
    thread.join()

#===============================================================================
# x-prefixed hex checksum (line 127)
#===============================================================================

def test_download_checksum_x_prefix(tmp_path, monkeypatch):
  monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / 'cache')
  content = b'x-prefix test content'
  (tmp_path / 'xhex.bin').write_bytes(content)
  digest_xhex = 'x' + hashlib.sha256(content).hexdigest()
  httpd, thread, base = start_server(tmp_path)
  try:
    url = f"{base}/xhex.bin"
    build_dir = tmp_path / 'build'
    build_dir.mkdir()
    logger = logging.getLogger('test')
    opts = {'url': url, 'checksum': f"sha256={digest_xhex}"}  # starts with 'x'
    download.download(None, logger, opts, tmp_path, tmp_path, build_dir, tmp_path, [], [], [], False, None)
    assert (build_dir / 'xhex.bin').is_symlink()
  finally:
    httpd.shutdown()
    thread.join()

#===============================================================================
# extract to a specific path (line 152) — extract is a str/Path, not just True
#===============================================================================

def test_download_extract_to_path(tmp_path, monkeypatch):
  monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / 'cache')
  tar_path, digest = create_tar(tmp_path)
  httpd, thread, base = start_server(tmp_path)
  try:
    url = f"{base}/file.tar"
    build_dir = tmp_path / 'build'
    build_dir.mkdir()
    extract_dir = tmp_path / 'extracted'
    extract_dir.mkdir()
    logger = logging.getLogger('test')
    opts = {
      'url': url,
      'checksum': f"sha256={digest}",
      'extract': str(extract_dir),  # path string → out_dir = extract (line 152)
    }
    download.download(None, logger, opts, tmp_path, tmp_path, build_dir, tmp_path, [], [], [], False, None)
    assert (extract_dir / 'inner.txt').read_text() == 'data'
  finally:
    httpd.shutdown()
    thread.join()

#===============================================================================
def test_cache_fallback(tmp_path, monkeypatch):

  def _nohome():
    raise RuntimeError()

  # NOTE: this test exercises 'cache_dir' itself, so the re-direction applied by
  # the 'isolate_cache_dir' fixture must be undone, or the fallback is never reached
  monkeypatch.setattr(cache, 'CACHE_DIR', None)
  monkeypatch.delenv('PARTIS_PYPROJ_CACHE_DIR', raising = False)

  monkeypatch.setattr(Path, "home", _nohome)
  dir = cache.cache_dir()

  assert dir.is_relative_to(Path(tempfile.gettempdir()))

#===============================================================================
def test_cache_dirname():
  # a cache entry holds a build environment, whose own paths must remain within
  # the Windows MAX_PATH limit, so the name may not grow with the source path
  long = '/a_very/deeply/nested' + 20*'/directory' + '/pkg-0.0.1-py3.13.14'
  name = cache.cache_dirname(long)

  # only the final component identifies what the entry is for
  assert name.endswith('pkg-0.0.1-py3.13.14')
  assert 'directory' not in name

  # the final component alone is not unique, the hash prefix separates entries
  assert cache.cache_dirname('/a/pkg') != cache.cache_dirname('/b/pkg')

  # a path and its string form give the same name
  assert cache.cache_dirname(Path(long)) == cache.cache_dirname(str(Path(long)))

