import os
import os.path as osp
import sys
import tempfile
import shutil
import logging

from pytest import (
  raises )

from partis.pyproj.backend import (
  UnsupportedOperation,
  backend_init,
  _VENV_ENV_EXCLUDE,
  _venv_env,
  _run_editable_cmd,
  _run_editable_py,
  get_requires_for_build_sdist,
  build_sdist,
  get_requires_for_build_wheel,
  prepare_metadata_for_build_wheel,
  build_wheel )
from partis.pyproj.pyproj import PyProjBase


#===============================================================================
def test_backend_basic():
  root = osp.join(osp.dirname(osp.abspath(__file__)), 'pkg_base' )

  a = backend_init(
    root = root )

  b = backend_init(
    root = root,
    logger = logging.getLogger( __name__ )  )

  with raises(FileNotFoundError):
    c = backend_init(
      root = osp.dirname(osp.abspath(__file__)) )


  cwd = os.getcwd()

  try:
    os.chdir( root )

    # currently does not return any additional requirements
    assert get_requires_for_build_sdist() == list()
    assert get_requires_for_build_wheel() == list()

    with tempfile.TemporaryDirectory() as tmpdir:

      name =  build_sdist( dist_directory = tmpdir )
      assert osp.exists( osp.join( tmpdir, name ) )

      name =  prepare_metadata_for_build_wheel( metadata_directory = tmpdir )
      assert osp.exists( osp.join( tmpdir, name) )

      name =  build_wheel( wheel_directory = tmpdir )
      assert osp.exists( osp.join( tmpdir, name) )

  finally:
    os.chdir( cwd )

#===============================================================================
def test_backend_init_no_logging():
  root = osp.join(osp.dirname(osp.abspath(__file__)), 'pkg_base')

  result = backend_init(root=root, init_logging=False)

  assert isinstance(result, PyProjBase)

#===============================================================================
def test_run_editable_cmd_missing_bin(tmp_path):
  with raises(FileNotFoundError):
    _run_editable_cmd(tmp_path, ['echo', 'hello'])

#===============================================================================
def test_run_editable_py_missing_interpreter(tmp_path):
  (tmp_path/'bin').mkdir()

  with raises(FileNotFoundError):
    _run_editable_py(tmp_path, ['-c', 'pass'])

#===============================================================================
def test_venv_env_scrub(tmp_path, monkeypatch):
  """The parent's interpreter path configuration is not forwarded into the venv
  """

  venv_bin = tmp_path/'bin'
  venv_bin.mkdir()

  for k in _VENV_ENV_EXCLUDE:
    monkeypatch.setenv(k, 'parent-value')

  monkeypatch.setenv('PATH', os.pathsep.join(['parent_bin', 'other_bin']))
  monkeypatch.setenv('PARTIS_PYPROJ_TEST_UNRELATED', 'kept')

  _bin, env = _venv_env(tmp_path)

  assert _bin == venv_bin
  assert not (_VENV_ENV_EXCLUDE & env.keys())

  # only the path configuration is dropped, the rest of the environment remains
  assert env['PARTIS_PYPROJ_TEST_UNRELATED'] == 'kept'
  assert env['VIRTUAL_ENV'] == str(tmp_path)
  assert env['PATH'].split(os.pathsep) == [str(venv_bin), 'parent_bin', 'other_bin']

#===============================================================================
def test_venv_env_no_path(tmp_path, monkeypatch):
  # 'bin' is absent, so the windows layout is used
  venv_bin = tmp_path/'Scripts'
  venv_bin.mkdir()

  monkeypatch.delenv('PATH', raising = False)

  _bin, env = _venv_env(tmp_path)

  # no empty entry, which would otherwise put the working directory on PATH
  assert _bin == venv_bin
  assert env['PATH'] == str(venv_bin)

#===============================================================================
def test_run_editable_cmd_scrub(tmp_path, monkeypatch):
  """The scrub reaches the spawned process, not only the mapping it is built from
  """

  (tmp_path/'bin').mkdir()

  for k in _VENV_ENV_EXCLUDE:
    monkeypatch.setenv(k, str(tmp_path/'overlay'))

  # exits non-zero, raising CalledProcessError, if any variable was inherited
  _run_editable_cmd(tmp_path, [
    sys.executable, '-c',
    'import os, sys;'
    f' sys.exit(len([k for k in {sorted(_VENV_ENV_EXCLUDE)!r} if k in os.environ]))'])
