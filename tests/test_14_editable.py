import os
import sys
from pathlib import Path
import subprocess
import shutil
import zipfile
import pytest
from unittest.mock import patch
from subprocess import check_call
from partis.pyproj import PyProjBase
from partis.pyproj.path import PathError
from partis.pyproj.validate import (
  FileOutsideRootError,
  ValidPathError)
from partis.pyproj.backend import (
  get_requires_for_build_editable,
  prepare_metadata_for_build_editable,
  build_editable,
  _run_editable_py)

pyversion = '.'.join(str(n) for n in sys.version_info[:3])

# Minimal package, used to check only where the editable root is placed
_TOML_MIN = """\
[project]
name = "test-editable-pkg"
version = "0.0.1"

[build-system]
requires = ["partis-pyproj"]
build-backend = "partis.pyproj.backend"

[tool.pyproj.dist.binary.purelib]
copy = []
"""

#===============================================================================
def _make_pkg(src, dst):
  shutil.copytree(src, dst)
  shutil.copyfile(Path(__file__).parent.parent/'.gitignore', dst/'.gitignore')

  subprocess.check_call(['git', 'init'], cwd=dst)
  subprocess.check_call(['git', 'add', '.'], cwd=dst)
  subprocess.check_call(['git', 'config', 'user.email', 'test@example.com'], cwd=dst)
  subprocess.check_call(['git', 'config', 'user.name', 'Tester'], cwd=dst)
  subprocess.check_call(['git', 'commit', '-m', 'init'], cwd=dst)

#===============================================================================
def _check_link(link: Path, target: Path):
  return link.is_symlink() and os.readlink(link).removeprefix("\\\\?\\") == str(target)

#===============================================================================
def _make_min_pkg(root: Path, build_dir = None) -> Path:
  root.mkdir(parents=True)
  toml = _TOML_MIN

  if build_dir is not None:
    toml += f'\n[tool.pyproj.editable]\nbuild_dir = "{build_dir}"\n'

  (root/'pyproject.toml').write_text(toml)
  return root

#===============================================================================
def test_build_editable_basic(tmp_path):
  root = tmp_path/'pkg'
  _make_pkg(Path(__file__).parent/'pkg_base', root)

  wheel_dir = tmp_path/'dist'
  meta_dir = tmp_path/'wheel_metadata'
  wheel_dir.mkdir()

  pkg = 'test_pkg'

  editable_root = root/'build'/'editable'/f'test_pkg_base_0.0.1_py{pyversion}'
  editable_root.mkdir(parents=True)
  whl_root = editable_root/'wheel'
  # should still work even if it already exists
  whl_root.mkdir()
  (whl_root/'dummy').touch()

  cwd = os.getcwd()

  try:
    os.chdir(root)
    deps = get_requires_for_build_editable()
    prepare_metadata_for_build_editable(meta_dir)
    name = build_editable(str(wheel_dir))
  finally:
    os.chdir(cwd)

  whl_path = wheel_dir/name
  assert whl_path.exists()
  assert whl_root.is_dir()

  with zipfile.ZipFile(whl_path) as zf:
    data = zf.read('test_pkg_base.pth').decode().splitlines()

  assert data == [str(whl_root)]

  link = whl_root/'test_pkg_base'/'pure_mod'/'pure_mod.py'
  print(f"{list((whl_root/'test_pkg_base').iterdir())=}")
  assert _check_link(link, root/'src'/'test_pkg'/'pure_mod'/'pure_mod.py')

#===============================================================================
def test_build_incremental(tmp_path):
  root = tmp_path/'pkg'
  print(f"{root=}")
  _make_pkg(Path(__file__).parent/'pkg_meson_1', root)

  wheel_dir = tmp_path/'dist'
  meta_dir = tmp_path/'wheel_metadata'
  wheel_dir.mkdir()

  cwd = os.getcwd()
  try:
    os.chdir(root)
    deps = get_requires_for_build_editable()
    prepare_metadata_for_build_editable(meta_dir)
    name = build_editable(str(wheel_dir))
  finally:
    os.chdir(cwd)

  whl_path = wheel_dir/name

  pkg = 'test_pkg_meson_1'
  editable_root = root/'build'/'editable'/f'{pkg}_0.0.1_py{pyversion}'
  whl_root = editable_root/'wheel'

  with zipfile.ZipFile(whl_path) as zf:
    pth_lines = zf.read(pkg + '.pth').decode().splitlines()

  assert pth_lines[0] == str(whl_root)

  link = whl_root/'test_pkg_meson_1'/'pure_mod.py'
  assert _check_link(link, root/'src'/'test_pkg'/'pure_mod.py')

  edited_src = root/'src'/'test_pkg'/'edited_mod.py'
  edited_text = "# test edited"
  edited_src.write_text(edited_text)

  edited_dst = whl_root/'test_pkg_meson_1'/edited_src.name
  assert not edited_dst.exists()

  check_call([
    'partis-pyproj', 'rebuild',
    str(root)])

  assert _check_link(edited_dst, edited_src)
  assert edited_dst.read_text() == edited_text

#===============================================================================
def test_editable_root_default(tmp_path):
  root = _make_min_pkg(tmp_path/'pkg')
  pyproj = PyProjBase(root = root, editable = True)

  assert pyproj.editable_root == (
    root/'build'/'editable'/f'test_editable_pkg_0.0.1_py{pyversion}')

#===============================================================================
def test_editable_root_configured(tmp_path):
  root = _make_min_pkg(tmp_path/'pkg', build_dir = 'staging/editable')
  pyproj = PyProjBase(root = root, editable = True)

  assert pyproj.editable_root == (
    root/'staging'/'editable'/f'test_editable_pkg_0.0.1_py{pyversion}')

#===============================================================================
def test_editable_root_outside_root(tmp_path):
  # relative path escaping the project root
  root = _make_min_pkg(tmp_path/'pkg_rel', build_dir = '../elsewhere')

  with pytest.raises(FileOutsideRootError):
    PyProjBase(root = root, editable = True)

  # absolute path outside the project root
  root = _make_min_pkg(
    tmp_path/'pkg_abs',
    build_dir = (tmp_path/'elsewhere').as_posix())

  with pytest.raises(FileOutsideRootError):
    PyProjBase(root = root, editable = True)

#===============================================================================
def test_editable_root_is_root(tmp_path):
  root = _make_min_pkg(tmp_path/'pkg', build_dir = '.')

  with pytest.raises(ValidPathError):
    PyProjBase(root = root, editable = True)

#===============================================================================
def test_editable_two_checkouts(tmp_path):
  """Two checkouts of the same package at the same version must not share a farm
  """
  src = Path(__file__).parent/'pkg_base'
  pkg = 'test_pkg_base'
  roots = list()

  for name in ('a', 'b'):
    root = tmp_path/name/'pkg'
    root.parent.mkdir()
    _make_pkg(src, root)
    roots.append(root)

  pth = list()
  cwd = os.getcwd()

  for i, root in enumerate(roots):
    wheel_dir = tmp_path/f'dist_{i}'
    wheel_dir.mkdir()

    try:
      os.chdir(root)
      prepare_metadata_for_build_editable(tmp_path/f'meta_{i}')
      name = build_editable(str(wheel_dir))
    finally:
      os.chdir(cwd)

    with zipfile.ZipFile(wheel_dir/name) as zf:
      lines = zf.read(pkg + '.pth').decode().splitlines()

    pth.append(Path(lines[0]))

  # each farm is under its own source tree, and building the second did not
  # remove or re-point the first
  for root, whl_root in zip(roots, pth):
    assert whl_root == root/'build'/'editable'/f'{pkg}_0.0.1_py{pyversion}'/'wheel'
    assert _check_link(
      whl_root/pkg/'pure_mod'/'pure_mod.py',
      root/'src'/'test_pkg'/'pure_mod'/'pure_mod.py')
