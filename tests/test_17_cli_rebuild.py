"""
Tests for cli/build_pyproj.py covering:
  - _prep_impl / _rebuild_impl: argparse dispatch wrappers
  - _prep_pyproj: basic call on a package with no targets/prep
  - _rebuild_pyproj: "editable root not found" branch → SystemExit(1)
  - _rebuild_pyproj: full rebuild, whl_root pre-exists → rmtree + recreate
  - _rebuild_pyproj: full rebuild, whl_root absent → create fresh (skips rmtree)
  - _rebuild_pyproj: configured 'tool.pyproj.editable.build_dir' is used
"""
import argparse
import os
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

from partis.pyproj.cli.build_pyproj import (
  _prep_impl, _rebuild_impl,
  _prep_pyproj, _rebuild_pyproj)

pyversion = '.'.join(str(n) for n in sys.version_info[:3])

# Minimal package — no targets, no prep, empty purelib copy
_TOML_NO_TARGETS = """\
[project]
name = "test-cli-pkg"
version = "0.0.1"

[build-system]
requires = ["partis-pyproj"]
build-backend = "partis.pyproj.backend"

[tool.pyproj.dist.binary.purelib]
copy = []
"""

# Package with one enabled process target (no commands — runs as a no-op)
_TOML_WITH_TARGETS = """\
[project]
name = "test-cli-targets-pkg"
version = "0.0.1"

[build-system]
requires = ["partis-pyproj"]
build-backend = "partis.pyproj.backend"

[tool.pyproj.dist.binary.purelib]
copy = []

[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
"""

_LEAF = f'test_cli_targets_pkg_0.0.1_py{pyversion}'

def _make_pkg(tmp_path, toml: str) -> Path:
  pkg = tmp_path / 'pkg'
  pkg.mkdir()
  (pkg / 'pyproject.toml').write_text(toml)
  return pkg

#===============================================================================
# _prep_pyproj
#===============================================================================

def test_prep_pyproj(tmp_path):
  # Package with no targets: dist_prep and dist_binary_prep are both no-ops
  pkg = _make_pkg(tmp_path, _TOML_NO_TARGETS)
  _prep_pyproj(path=pkg)  # must complete without error

#===============================================================================
# _rebuild_pyproj — "editable root not found" branch
#===============================================================================

def test_rebuild_editable_not_found(tmp_path):
  # the default editable root was never created → exit(1)
  pkg = _make_pkg(tmp_path, _TOML_WITH_TARGETS)
  with pytest.raises(SystemExit) as exc:
    _rebuild_pyproj(root=pkg)
  assert exc.value.code == 1

#===============================================================================
# _rebuild_pyproj — full rebuild
#===============================================================================

def test_rebuild_full(tmp_path):
  pkg = _make_pkg(tmp_path, _TOML_WITH_TARGETS)

  editable_root = pkg / 'build' / 'editable' / _LEAF

  # Pre-populate whl_root so the shutil.rmtree branch is taken
  whl_root = editable_root / 'wheel'
  whl_root.mkdir(parents=True)
  stale = whl_root / 'stale.so'
  stale.touch()

  # _run_editable_py requires a real venv; mock it out
  with patch('partis.pyproj.cli.build_pyproj._run_editable_py'):
    _rebuild_pyproj(root=pkg)

  # whl_root was removed and recreated by dist_binary_editable.create_distfile
  assert whl_root.is_dir()
  assert not stale.exists()

#===============================================================================
# _rebuild_pyproj — full rebuild, whl_root absent → skip rmtree
#===============================================================================

def test_rebuild_full_no_existing_wheel(tmp_path):
  pkg = _make_pkg(tmp_path, _TOML_WITH_TARGETS)
  editable_root = pkg / 'build' / 'editable' / _LEAF
  editable_root.mkdir(parents=True)
  # whl_root does not pre-exist → if whl_root.exists() is False → skip rmtree

  with patch('partis.pyproj.cli.build_pyproj._run_editable_py'):
    _rebuild_pyproj(root=pkg)

  assert (editable_root / 'wheel').is_dir()

#===============================================================================
# _rebuild_pyproj — configured build_dir
#===============================================================================

def test_rebuild_configured_build_dir(tmp_path):
  pkg = _make_pkg(
    tmp_path,
    _TOML_WITH_TARGETS + '\n[tool.pyproj.editable]\nbuild_dir = "staging"\n')

  editable_root = pkg / 'staging' / _LEAF
  editable_root.mkdir(parents=True)

  with patch('partis.pyproj.cli.build_pyproj._run_editable_py'):
    _rebuild_pyproj(root=pkg)

  assert (editable_root / 'wheel').is_dir()
  assert not (pkg / 'build' / 'editable').exists()

#===============================================================================
# _prep_impl / _rebuild_impl — argparse dispatch wrappers
#===============================================================================

def test_prep_impl(tmp_path):
  pkg = _make_pkg(tmp_path, _TOML_NO_TARGETS)
  _prep_impl(argparse.Namespace(path=pkg))

def test_rebuild_impl(tmp_path):
  pkg = _make_pkg(tmp_path, _TOML_WITH_TARGETS)
  with pytest.raises(SystemExit) as exc:
    _rebuild_impl(argparse.Namespace(root=pkg))
  assert exc.value.code == 1
