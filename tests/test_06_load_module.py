import os
import os.path as osp
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from pytest import (
  raises )

from partis.pyproj.load_module import (
  module_name_from_path,
  load_module,
  load_entrypoint,
  EntryPoint,
  EntryPointError )

from partis.pyproj.validate import ValidationError

#===============================================================================
def test_load_entrypoint():
  root = Path(__file__).parent / 'pkg_base'


  f = load_entrypoint('pkgaux:dist_prep', root)

  assert callable(f)

  with raises( ValueError ):
    load_entrypoint('pkgaux:not_an_attr', root)

#===============================================================================
def test_module_name_from_path_empty():
  root = Path('/some/root')
  with raises(EntryPointError, match='Empty module name'):
    module_name_from_path(root, root)

#===============================================================================
def test_load_entrypoint_import_error():
  root = Path('/nonexistent/root')
  with raises(EntryPointError):
    load_entrypoint('nonexistent_stdlib_module_xyz:func', root)

#===============================================================================
def test_load_entrypoint_reraises_entry_point_error():
  root = Path(__file__).parent / 'pkg_base'
  inner = EntryPointError('inner error')
  with patch('partis.pyproj.load_module.load_module', side_effect=inner):
    with raises(EntryPointError, match='inner error'):
      load_entrypoint('pkgaux:dist_prep', root)

#===============================================================================
def test_load_entrypoint_wraps_generic_exception():
  root = Path(__file__).parent / 'pkg_base'
  with patch('partis.pyproj.load_module.load_module', side_effect=RuntimeError('boom')):
    with raises(EntryPointError):
      load_entrypoint('pkgaux:dist_prep', root)

#===============================================================================
def test_entry_point_call_reraises_validation_error():
  root = Path(__file__).parent / 'pkg_base'

  mock_func = MagicMock(side_effect=ValidationError('validation failed'))
  mock_logger = MagicMock()

  ep = object.__new__(EntryPoint)
  ep.pyproj = None
  ep.root = root
  ep.name = 'test_ep'
  ep.logger = mock_logger
  ep.entry = 'pkgaux:dist_prep'
  ep.func = mock_func

  with raises(ValidationError):
    ep()
