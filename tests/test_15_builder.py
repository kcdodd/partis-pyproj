"""
Tests for Builder and ProcessRunner covering:
  - ProcessRunner: empty command, missing executable, CalledProcessError formatter
  - Builder.build_targets: exclusive group validation and skip (including continue bug fix)
  - Builder.build_targets: build-dirty / incremental / env-change detection
  - Builder.build_targets: target validation errors (src_dir, build_dir, prefix)
  - Builder.build_targets: per-target env template substitution
"""
import sys
import os
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from partis.pyproj import ValidationError, PyProjBase
from partis.pyproj.validate import ValidPathError
from partis.pyproj.builder.builder import ProcessRunner, BuildCommandError, Builder
from partis.pyproj.builder.cmake import cmake
from partis.pyproj.builder.meson import meson

#===============================================================================
# Helpers
#===============================================================================

def _runner(tmp_path):
  logs = tmp_path / 'logs'
  logs.mkdir(exist_ok=True)
  return ProcessRunner(
    logger=logging.getLogger('test_builder'),
    log_dir=logs,
    target_name='t00',
    env=os.environ.copy())

_BASE_TOML = """\
[project]
name = "test-builder-pkg"
version = "0.0.1"

[build-system]
requires = ["partis-pyproj"]
build-backend = "partis.pyproj.backend"

[tool.pyproj.dist.binary.purelib]
copy = []
"""

def _make_pyproj(tmp_path, extra=''):
  pkg = tmp_path / 'pkg'
  pkg.mkdir(exist_ok=True)
  (pkg / 'pyproject.toml').write_text(_BASE_TOML + '\n' + extra)
  return PyProjBase(root=pkg), pkg

def _builder(pyproj, pkg, editable=False):
  return Builder(
    pyproj=pyproj,
    root=pkg,
    targets=pyproj.targets,
    logger=pyproj.logger,
    editable=editable)

#===============================================================================
# ProcessRunner
#===============================================================================

def test_runner_empty_command(tmp_path):
  with pytest.raises(ValueError, match='is empty'):
    _runner(tmp_path).run([])

def test_runner_missing_executable(tmp_path):
  with pytest.raises(ValidationError, match='Executable does not exist'):
    _runner(tmp_path).run(['_partis_nonexistent_cmd_xyz_'])

def test_runner_failed_command(tmp_path):
  # CalledProcessError triggers the output-formatter block (lines 399-444).
  # Output contains "ERROR:" so suspect_linenos is non-empty, and last_lines non-empty.
  with pytest.raises(BuildCommandError) as exc_info:
    _runner(tmp_path).run([
      sys.executable, '-c',
      'import sys; print("ERROR: intentional failure"); sys.exit(1)'])
  assert 'ERROR: intentional failure' in str(exc_info.value)

def test_runner_failed_no_output(tmp_path):
  # Failure with no output: suspect_linenos and last_lines are both empty (different branches).
  with pytest.raises(BuildCommandError):
    _runner(tmp_path).run([sys.executable, '-c', 'import sys; sys.exit(1)'])

#===============================================================================
# Exclusive group
#===============================================================================

_EXCL_BOTH_DISABLED = """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
exclusive = "grp"
enabled = false

[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
exclusive = "grp"
enabled = false
"""

def test_exclusive_all_disabled(tmp_path):
  # No enabled target in the exclusive group → ValidationError
  pyproj, pkg = _make_pyproj(tmp_path, _EXCL_BOTH_DISABLED)
  with _builder(pyproj, pkg) as b:
    with pytest.raises(ValidationError, match='does not have an enabled target'):
      b.build_targets()

_EXCL_TWO_ENABLED = """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
exclusive = "grp"

[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
exclusive = "grp"
"""

def test_exclusive_second_skipped(tmp_path, caplog):
  # Two enabled targets in the same exclusive group: first runs, second is skipped.
  # The missing 'continue' bug would cause targets[1] to also execute.
  pyproj, pkg = _make_pyproj(tmp_path, _EXCL_TWO_ENABLED)
  with caplog.at_level(logging.DEBUG):
    with _builder(pyproj, pkg) as b:
      b.build_targets()

  assert any('already satisfied' in m for m in caplog.messages), \
    "Expected skip-warning for second exclusive target"
  assert not any('targets[1]:' in m for m in caplog.messages), \
    "Second exclusive target must not execute (missing 'continue' bug)"

#===============================================================================
# Build-dirty / incremental detection
#===============================================================================

_PROCESS_TARGET = """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
"""

_PROCESS_TARGET_WITH_ENV = """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"

[tool.pyproj.targets.env]
PYPROJ_TEST_VAR = "hello"
"""

def test_build_dirty_incremental(tmp_path):
  # Editable build: second run with unchanged environment must not clean build_dir.
  pyproj, pkg = _make_pyproj(tmp_path, _PROCESS_TARGET)
  build_dir = pkg / 'build' / 'tmp'

  with _builder(pyproj, pkg, editable=True) as b:
    b.build_targets()

  assert (build_dir / '.pyproj_status').exists()
  original_status = (build_dir / '.pyproj_status').read_text()

  # Marker to detect whether the directory was cleaned
  marker = build_dir / 'incremental_artifact.o'
  marker.write_bytes(b'artifact')

  with _builder(pyproj, pkg, editable=True) as b:
    b.build_targets()

  assert marker.exists(), "build_dir was cleaned on incremental rebuild (should not be)"
  assert (build_dir / '.pyproj_status').read_text() == original_status

def test_build_dirty_env_change(tmp_path, caplog):
  # Editable build: stale status file → builder must clean and rebuild.
  pyproj, pkg = _make_pyproj(tmp_path, _PROCESS_TARGET)
  build_dir = pkg / 'build' / 'tmp'
  build_dir.mkdir(parents=True)
  (build_dir / '.pyproj_status').write_text('stale content from previous environment')
  marker = build_dir / 'stale_artifact.o'
  marker.write_bytes(b'artifact')

  with caplog.at_level(logging.INFO):
    with _builder(pyproj, pkg, editable=True) as b:
      b.build_targets()

  assert not marker.exists(), "build_dir was not cleaned despite env change"
  assert any('Change in environment' in m for m in caplog.messages)

def test_build_dirty_raises_no_status(tmp_path):
  # Non-editable (build_clean=True): dirty build_dir with no status file → ValidPathError.
  pyproj, pkg = _make_pyproj(tmp_path, _PROCESS_TARGET)
  build_dir = pkg / 'build' / 'tmp'
  build_dir.mkdir(parents=True)
  (build_dir / 'stale.o').write_bytes(b'stale')  # dirty, no .pyproj_status

  with _builder(pyproj, pkg, editable=False) as b:
    with pytest.raises(ValidPathError, match='not empty'):
      b.build_targets()

#===============================================================================
# Target path validation errors
#===============================================================================

def test_build_dir_is_root(tmp_path):
  pyproj, pkg = _make_pyproj(tmp_path, """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
build_dir = "."
""")
  with _builder(pyproj, pkg) as b:
    with pytest.raises(ValidPathError, match="cannot be project root"):
      b.build_targets()

def test_src_dir_not_found(tmp_path):
  pyproj, pkg = _make_pyproj(tmp_path, """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
src_dir = "nonexistent_src_dir"
""")
  with _builder(pyproj, pkg) as b:
    with pytest.raises(ValidPathError, match="Source directory not found"):
      b.build_targets()

def test_src_dir_is_file(tmp_path):
  pyproj, pkg = _make_pyproj(tmp_path, """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
src_dir = "pyproject.toml"
""")
  with _builder(pyproj, pkg) as b:
    with pytest.raises(ValidPathError, match="not a directory"):
      b.build_targets()

def test_prefix_inside_build_dir(tmp_path):
  pyproj, pkg = _make_pyproj(tmp_path, """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
build_dir = "build/tmp"
prefix = "build/tmp/nested"
""")
  with _builder(pyproj, pkg) as b:
    with pytest.raises(ValidPathError, match="inside 'build_dir'"):
      b.build_targets()

#===============================================================================
# Exclusive group with mixed exclusive/non-exclusive targets
#===============================================================================

_EXCL_MIXED = """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
exclusive = "grp"

[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
"""

def test_exclusive_with_non_exclusive_target(tmp_path):
  # One exclusive target + one non-exclusive target: both should run,
  # hitting the 'continue' for non-exclusive entries in the pre-scan loop.
  pyproj, pkg = _make_pyproj(tmp_path, _EXCL_MIXED)
  with _builder(pyproj, pkg) as b:
    b.build_targets()  # must complete without error

#===============================================================================
# Shared build_dir across two targets
#===============================================================================

_TWO_SHARED_BUILD_DIR = """\
[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
build_dir = "build/shared"

[[tool.pyproj.targets]]
entry = "partis.pyproj.builder:process"
build_dir = "build/shared"
"""

def test_shared_build_dir(tmp_path):
  # Two targets with the same build_dir: the status-file check is done once
  # and skipped for the second target (hits the 'already in status_files' branch).
  pyproj, pkg = _make_pyproj(tmp_path, _TWO_SHARED_BUILD_DIR)
  with _builder(pyproj, pkg) as b:
    b.build_targets()  # must complete without error

#===============================================================================
# Per-target env template substitution (lines 267-269)
#===============================================================================

def test_env_substitution(tmp_path):
  # A target with an 'env' table exercises the substitution loop.
  pyproj, pkg = _make_pyproj(tmp_path, _PROCESS_TARGET_WITH_ENV)
  with _builder(pyproj, pkg) as b:
    b.build_targets()  # must complete without error

#===============================================================================
# cmake / meson missing executable
#===============================================================================

def _make_cmake_args(tmp_path):
  pyproj, pkg = _make_pyproj(tmp_path)
  runner = MagicMock()
  return dict(
    pyproj=pyproj,
    logger=pyproj.logger,
    options={},
    work_dir=pkg,
    src_dir=pkg,
    build_dir=tmp_path / 'build',
    prefix=tmp_path / 'prefix',
    setup_args=[],
    compile_args=[],
    install_args=[],
    build_clean=True,
    runner=runner)

def _make_meson_args(tmp_path):
  pyproj, pkg = _make_pyproj(tmp_path)
  runner = MagicMock()
  return dict(
    pyproj=pyproj,
    logger=pyproj.logger,
    options={},
    work_dir=pkg,
    src_dir=pkg,
    build_dir=tmp_path / 'build',
    prefix=tmp_path / 'prefix',
    setup_args=[],
    compile_args=[],
    install_args=[],
    build_clean=True,
    runner=runner)

def test_cmake_missing_cmake(tmp_path):
  args = _make_cmake_args(tmp_path)
  with patch('shutil.which', return_value=None):
    with pytest.raises(ValueError, match="cmake"):
      cmake(**args)

def test_cmake_missing_ninja(tmp_path):
  args = _make_cmake_args(tmp_path)
  def _which(name):
    return '/usr/bin/cmake' if name == 'cmake' else None
  with patch('shutil.which', side_effect=_which):
    with pytest.raises(ValueError, match="ninja"):
      cmake(**args)

def test_meson_missing_meson(tmp_path):
  args = _make_meson_args(tmp_path)
  with patch('shutil.which', return_value=None):
    with pytest.raises(ValueError, match="meson"):
      meson(**args)

def test_meson_missing_ninja(tmp_path):
  args = _make_meson_args(tmp_path)
  def _which(name):
    return '/usr/bin/meson' if name == 'meson' else None
  with patch('shutil.which', side_effect=_which):
    with pytest.raises(ValueError, match="ninja"):
      meson(**args)

#===============================================================================
# build_clean=False skips setup
#===============================================================================

def test_cmake_build_clean_false_skips_setup(tmp_path):
  args = _make_cmake_args(tmp_path)
  args['build_clean'] = False
  args['build_dir'].mkdir(parents=True)
  runner = args['runner']
  def _which(name):
    return f'/usr/bin/{name}'
  with patch('shutil.which', side_effect=_which):
    cmake(**args)
  calls = [str(c) for c in runner.run.call_args_list]
  assert not any('cmake' in c and '-S' in c for c in calls), \
    "cmake configure should be skipped when build_clean=False"
  assert runner.run.call_count == 2

def test_meson_build_clean_false_skips_setup(tmp_path):
  args = _make_meson_args(tmp_path)
  args['build_clean'] = False
  args['build_dir'].mkdir(parents=True)
  runner = args['runner']
  def _which(name):
    return f'/usr/bin/{name}'
  with patch('shutil.which', side_effect=_which):
    meson(**args)
  calls = [str(c) for c in runner.run.call_args_list]
  assert not any('setup' in c for c in calls), \
    "meson setup should be skipped when build_clean=False"
  assert runner.run.call_count == 2
