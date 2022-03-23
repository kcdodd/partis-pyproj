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
def test_base():

  with tempfile.TemporaryDirectory() as tmpdir:

    outdir = osp.join(tmpdir, 'dist')
    pkg_dir = osp.join( tmpdir, 'pkg_base' )

    shutil.copytree(
      osp.join(osp.dirname(osp.abspath(__file__)), 'pkg_base' ),
      pkg_dir )

    cwd = os.getcwd()

    try:
      os.chdir(pkg_dir)

      pyproj = PyProjBase(
        root = pkg_dir )

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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_meson():

  with tempfile.TemporaryDirectory() as tmpdir:

    outdir = osp.join(tmpdir, 'dist')
    pkg_dir = osp.join( tmpdir, 'pkg_meson' )

    shutil.copytree(
      osp.join(osp.dirname(osp.abspath(__file__)), 'pkg_meson' ),
      pkg_dir )

    cwd = os.getcwd()

    try:
      os.chdir(pkg_dir)

      pyproj = PyProjBase(
        root = pkg_dir )

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
