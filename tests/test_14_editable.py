import os
import sys
from pathlib import Path
import subprocess
import shutil
import zipfile
import pytest
from unittest.mock import patch
from subprocess import check_call
from partis.pyproj import cache
from partis.pyproj.path import PathError
from partis.pyproj.backend import (
  get_requires_for_build_editable,
  prepare_metadata_for_build_editable,
  build_editable,
  _run_editable_py)

pyversion = '.'.join(str(n) for n in sys.version_info[:3])

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
def test_build_editable_basic(tmp_path, monkeypatch):
  root = tmp_path/'pkg'
  _make_pkg(Path(__file__).parent/'pkg_base', root)

  wheel_dir = tmp_path/'dist'
  meta_dir = tmp_path/'wheel_metadata'
  wheel_dir.mkdir()

  cache_dir = tmp_path/'.cache'
  cache_dir.mkdir()
  monkeypatch.setattr(cache, "CACHE_DIR", cache_dir)

  pkg = 'test_pkg'

  editable_root = cache_dir/'editable'/f'test_pkg_base_0.0.1_py{pyversion}'
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
def test_build_incremental(tmp_path, monkeypatch):
  root = tmp_path/'pkg'
  print(f"{root=}")
  _make_pkg(Path(__file__).parent/'pkg_meson_1', root)

  wheel_dir = tmp_path/'dist'
  meta_dir = tmp_path/'wheel_metadata'
  wheel_dir.mkdir()

  cache_dir = tmp_path/'.cache'
  cache_dir.mkdir()
  monkeypatch.setattr(cache, "CACHE_DIR", cache_dir)

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
  editable_root = cache_dir/'editable'/f'{pkg}_0.0.1_py{pyversion}'
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
    '--staging', str(editable_root),
    str(root)])

  assert _check_link(edited_dst, edited_src)
  assert edited_dst.read_text() == edited_text
