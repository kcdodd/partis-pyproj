import os
import os.path as osp
import tempfile
import shutil
import logging

from pytest import (
  raises )

from partis.pyproj.backend import (
  UnsupportedOperation,
  backend_init,
  _run_editable_cmd,
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
