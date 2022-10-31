import os
import os.path as osp
import tempfile
import shutil
from pathlib import Path

from pytest import (
  raises )

from partis.pyproj.load_module import (
  module_name_from_path,
  load_module,
  load_entrypoint )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_load_entrypoint():
  root = Path(__file__).parent / 'pkg_base'


  f = load_entrypoint('pkgaux:dist_prep', root)

  assert callable(f)

  with raises( ValueError ):
    load_entrypoint('pkgaux:not_an_attr', root)
