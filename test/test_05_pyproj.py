import sys
import os
import os.path as osp
import tempfile
import shutil
import subprocess
import glob

from pytest import (
  mark,
  warns,
  raises )

from partis.pyproj import (
  ValidationError,
  FileOutsideRootError,
  ValidationWarning,
  EntryPointError,
  PyProjBase,
  dist_source_targz,
  dist_binary_wheel )

SKIP_MESON = False

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def uninstall( name, ignore_errors = False ):

  try:
    subprocess.check_call([
      sys.executable,
      '-m',
      'pip',
      'uninstall',
      '-y',
      name ])
  except Exception as e:
    if ignore_errors:
      pass
    else:
      raise e

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def install( name ):
  subprocess.check_call([
    sys.executable,
    '-m',
    'pip',
    'install',
    name ])

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def try_dist(
  import_name,
  install_name ):

  # ensure not installed, e.g. from a previous test
  uninstall(
    import_name,
    ignore_errors = True )

  # install built test distribution
  install( install_name )

  # ensure the installation leads to importable module
  __import__( import_name )

  # should be able to succesfully uninstall (don't ignore errors)
  uninstall( import_name )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def try_legacy( name, dist_file ):
  # ensure not installed, e.g. from a previous test
  uninstall(
    name,
    ignore_errors = True )

  with tempfile.TemporaryDirectory() as tmpdir:

    cwd = os.getcwd()

    try:
      os.chdir(tmpdir)

      import tarfile

      with tarfile.open( dist_file ) as fp:

        fp.extractall('.')

      dist_dir = osp.join( tmpdir, osp.basename(dist_file)[:-7] )

      os.chdir(dist_dir)

      subprocess.check_call([
        sys.executable,
        'setup.py',
        'egg_info',
        '-e',
        tmpdir ])

      print(os.listdir(tmpdir))

      egg_info = next(iter(glob.glob(tmpdir + '/*.egg-info')))

      assert osp.isdir(egg_info)

      egg_files = os.listdir(egg_info)

      assert (
        set(egg_files) == set([
          'PKG-INFO',
          'setup_requires.txt',
          'requires.txt',
          'SOURCES.txt',
          'top_level.txt',
          'entry_points.txt',
          'dependency_links.txt',
          'not-zip-safe' ]) )

      subprocess.check_call([
        sys.executable,
        'setup.py',
        'bdist_wheel',
        '-d',
        tmpdir ])

      print(os.listdir(tmpdir))

      wheel_file = next(iter(glob.glob(tmpdir + '/*.whl')))

      try_dist(
        import_name = name,
        install_name = wheel_file )

      subprocess.check_call([
        sys.executable,
        'setup.py',
        'install' ])

      __import__( name )

      # should be able to succesfully uninstall (don't ignore errors)
      uninstall( name )

    finally:
      os.chdir(cwd)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def run_pyproj( name, source = True, binary = True ):

  with tempfile.TemporaryDirectory() as tmpdir:

    outdir = osp.join(tmpdir, 'dist')
    pkg_dir = osp.join( tmpdir, name )

    shutil.copytree(
      osp.join(osp.dirname(osp.abspath(__file__)), name ),
      pkg_dir,
      # some tests require copying symlinks
      symlinks = True )

    cwd = os.getcwd()

    try:
      os.chdir(pkg_dir)

      pyproj = PyProjBase(
        root = pkg_dir )

      pyproj.dist_prep()

      # build and install source dist
      if source:
        pyproj.dist_source_prep()

        with dist_source_targz(
          pkg_info = pyproj.pkg_info,
          outdir = outdir,
          logger = pyproj.logger ) as dist:

          pyproj.dist_source_copy(
            dist = dist )

        try_dist(
          import_name = pyproj.pkg_info.name,
          install_name = dist.outpath )

        if pyproj.add_legacy_setup:
          try_legacy(
            name = pyproj.pkg_info.name,
            dist_file = dist.outpath )

      # build and install binary dist
      if binary:
        pyproj.dist_binary_prep()

        with dist_binary_wheel(
          pkg_info = pyproj.pkg_info,
          compat = pyproj.binary.compat_tags,
          outdir = outdir,
          logger = pyproj.logger ) as dist:

          pyproj.dist_binary_copy(
            dist = dist )

        try_dist(
          import_name = pyproj.pkg_info.name,
          install_name = dist.outpath )

    finally:
      os.chdir(cwd)


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_min():
  run_pyproj('pkg_min')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_base():
  run_pyproj('pkg_base')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_bad_1():
  with raises(EntryPointError):
    # declares non-existent entrypoint
    run_pyproj('pkg_bad_1')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_bad_2():
  with raises(EntryPointError):
    # entrypoint raises exception
    run_pyproj('pkg_bad_2')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_bad_3():
  with raises(ValidationError):
    # declares dynamic but no entry-point
    run_pyproj('pkg_bad_3')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_bad_4():
  with raises(ValidationError):
    # changes meta-data without declaring dynamic
    run_pyproj('pkg_bad_4')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_bad_5():
  with warns(ValidationWarning):
    # declares dynamic but doesn't update
    run_pyproj('pkg_bad_5')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@mark.skipif(SKIP_MESON, reason="")
def test_meson_1():
  run_pyproj('pkg_meson_1')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
@mark.skipif(SKIP_MESON, reason="")
def test_meson_2():
  run_pyproj('pkg_meson_2')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# TODO: this test is broken
@mark.skipif(SKIP_MESON, reason="")
def test_meson_bad_1():
  with raises(FileOutsideRootError):
    # symlink points outside of root, cannot copy into distro
    run_pyproj(
      'pkg_meson_bad_1',
      source = True,
      binary = False )

  with raises(FileOutsideRootError):
    # symlink points outside of root, cannot use as meson 'prefix'
    run_pyproj(
      'pkg_meson_bad_1',
      source = False,
      binary = True )
