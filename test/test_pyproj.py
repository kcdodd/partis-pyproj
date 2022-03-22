import os
import os.path as osp
import tempfile
import shutil

from pytest import (
  raises )

from partis.pyproj import (
  PyProjBase,
  dist_source_targz,
  dist_binary_wheel )


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_meson():
  with tempfile.TemporaryDirectory() as tmpdir:

    outdir = osp.join(tmpdir, 'dist')

    shutil.copytree(
      osp.join(osp.dirname(osp.abspath(__file__)), 'pkg_tmpl' ),
      tmpdir,
      dirs_exist_ok = True )

    cwd = os.getcwd()

    try:
      os.chdir(tmpdir)
      
      pyproj = PyProjBase(
        root = tmpdir )

      pyproj.dist_prep()

      pyproj.dist_source_prep()

      with dist_source_targz(
        pkg_info = pyproj.pkg_info,
        outdir = outdir,
        logger = pyproj.logger ) as dist:

        pyproj.dist_source_copy(
          dist = dist )

      compat_tags = pyproj.dist_binary_prep()

      with dist_binary_wheel(
        pkg_info = pyproj.pkg_info,
        compat = compat_tags,
        outdir = outdir,
        logger = pyproj.logger ) as dist:

        pyproj.dist_binary_copy(
          dist = dist )
    finally:
      os.chdir(cwd)
