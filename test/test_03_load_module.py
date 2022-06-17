import os
import os.path as osp
import tempfile
import shutil

from pytest import (
  raises )

from partis.pyproj.load_module import (
  module_name_from_path,
  load_module,
  load_entrypoint )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_name():

  assert module_name_from_path(osp.join('a','b','c'), '') == "a.b.c"
  assert module_name_from_path(osp.join('a', 'b', 'c', 'd'), osp.join('a','b')) == "c.d"

  with raises(ValueError):
    # no module name
    module_name_from_path("", "")

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_load_module():
  root = osp.dirname(osp.abspath(__file__))

  mod = load_module( osp.join(root, "pkg_base", "pkgaux" ), root )

  print(dir(mod))
  assert callable(mod.dist_prep)

  with raises( ValueError ):
    load_module( osp.join(root, "not_a_directory" ), root )

  with raises( ValueError ):
    # not a module
    load_module( osp.join(root, "pkg_base" ), root )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_load_entrypoint():
  root = osp.dirname(osp.abspath(__file__))

  f = load_entrypoint('pkg_base.pkgaux:dist_prep', root)

  assert callable(f)

  with raises( ValueError ):
    load_entrypoint('pkg_base.pkgaux:not_an_attr', root)
