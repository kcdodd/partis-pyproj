import os
import os.path as osp
import tempfile
import shutil
import subprocess

from pytest import (
  raises )

from partis.pyproj import (
  PyProjBase,
  dist_source_targz,
  dist_binary_wheel )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def run_pyproj( name ):

  with tempfile.TemporaryDirectory() as tmpdir:

    outdir = osp.join(tmpdir, 'dist')
    pkg_dir = osp.join( tmpdir, name )

    shutil.copytree(
      osp.join(osp.dirname(osp.abspath(__file__)), name ),
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

      subprocess.check_call([
        'python3',
        '-m',
        'pip',
        'install',
        dist.outpath ])

      __import__(pyproj.pkg_info.name)

    finally:
      os.chdir(cwd)


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_min():

  run_pyproj('pkg_min')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_base():

  run_pyproj('pkg_base')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_meson():

  run_pyproj('pkg_meson')
