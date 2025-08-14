import http.server
import socketserver
import threading
import tarfile
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
    monkeypatch.setattr(download, "CACHE_DIR", tmp_path)
    url = "https://example.com/a b/c?d=e"
    checksum = "sha256=deadbeef"
    path = download._cached_download(url, checksum)
    # ensure filename sanitized
    assert " " not in str(path)
    info = path.with_name(path.name + ".info")
    assert info.read_text() == f"{url}\n{checksum}"


def test_download_extracts_and_sets_exec(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "CACHE_DIR", tmp_path / "cache")
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
    monkeypatch.setattr(download, "CACHE_DIR", tmp_path / "cache")
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
