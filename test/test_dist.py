import os
import os.path as osp
import tempfile
import shutil

from pytest import (
  raises )

from partis.pyproj import (
  PkgInfo,
  dist_base,
  dist_targz,
  dist_zip,
  dist_source_targz,
  dist_source_dummy,
  dist_binary_wheel )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_dist_source_dummy():

  with raises( ValueError ):
    dist_source_dummy( pkg_info = None )

  pkg_info = PkgInfo(
    project = dict(
      name = 'my-package',
      version = '1.0' ) )

  dist_source_dummy( pkg_info = pkg_info )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_dist_targz():

  dist = dist_targz('asd.tgz')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_dist_zip():

  dist = dist_zip('asd.zip')

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_dist_source():

  with raises( ValueError ):
    dist_source_targz( pkg_info = None )

  with tempfile.TemporaryDirectory() as tmpdir:

    pkg_dir = osp.join( tmpdir, 'src', 'my_package' )
    out_dir = osp.join( tmpdir, 'build' )
    mod_file = osp.join( pkg_dir, 'module.py' )

    os.makedirs( pkg_dir )

    with open( mod_file, 'w' ) as fp:
      fp.write("print('hello')")


    pkg_info = PkgInfo(
      project = dict(
        name = 'my-package',
        version = '1.0' ) )

    with dist_source_targz(
      pkg_info = pkg_info,
      outdir = out_dir ) as sdist:

      with raises( ValueError ):
        # already open
        sdist.open()

      sdist.copytree(
        src = osp.join( tmpdir, 'src' ),
        dst = osp.join( sdist.base_path, 'src' ),
        ignore = shutil.ignore_patterns('nothing') )

      with raises( ValueError ):
        # duplicate
        sdist.copytree(
          src = osp.join( tmpdir, 'src' ),
          dst = osp.join( sdist.base_path, 'src' ) )

      sdist.copyfile(
        src = mod_file,
        dst = osp.join( sdist.base_path, 'src', 'mod.py' ) )

      with raises( ValueError ):
        # duplicate
        sdist.copyfile(
          src = mod_file,
          dst = osp.join( sdist.base_path, 'src', 'mod.py' ) )

      with raises( ValueError ):
        # doesn't exist
        sdist.copyfile(
          src = 'asd',
          dst = 'xyz' )

      with raises( ValueError ):
        # doesn't exist
        sdist.copytree(
          src = 'asd',
          dst = 'xyz' )

    # already closed
    sdist.close()

    with raises( ValueError ):
      sdist.copytree(
        src = osp.join( tmpdir, 'src' ),
        dst = osp.join( sdist.base_path, 'src2' ) )

    assert sdist.outname == 'my_package-1.0.tar.gz'
    assert osp.relpath( sdist.outpath, tmpdir ) == 'build/my_package-1.0.tar.gz'
    assert osp.exists(sdist.outpath)

    # overwrite existing file
    sdist = dist_source_targz(
      pkg_info = pkg_info,
      outdir = out_dir )

    sdist.open()

    with sdist:

      sdist.copytree(
        src = osp.join( tmpdir, 'src' ),
        dst = osp.join( sdist.base_path, 'src' ) )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_dist_binary_wheel():



  with tempfile.TemporaryDirectory() as tmpdir:
    pkg_dir = osp.join( tmpdir, 'src', 'my_package' )
    out_dir = osp.join( tmpdir, 'build' )

    os.makedirs( pkg_dir )

    with open( osp.join( pkg_dir, 'module.py' ), 'w' ) as fp:
      fp.write("print('hello')")


    license_file = osp.join(tmpdir, 'license.rst')

    with open(license_file, 'w') as fp:
      fp.write("my license")


    pkg_info = PkgInfo(
      root = tmpdir,
      project = dict(
        name = 'my-package',
        version = '1.0',
        license = { 'file' : 'license.rst' } ) )

    pkg_info_dynamic = PkgInfo(
      project = dict(
        name = 'my-package',
        version = '1.0',
        dynamic = ['dependencies'] ) )

    with raises( ValueError ):
      dist_binary_wheel( pkg_info = None )

    with raises( ValueError ):
      dist_binary_wheel( pkg_info = pkg_info_dynamic )


    dist_binary_wheel( pkg_info = pkg_info )


    with dist_binary_wheel(
      pkg_info = pkg_info,
      outdir = out_dir,
      compat = [ ( 'py3', 'none', 'any' ), ],
      gen_name = 'custom' ) as bdist:

      for k in bdist.named_dirs.keys():

        bdist.copytree(
          src = pkg_dir,
          dst = bdist.named_dirs[k] + '/my_package' )

    assert bdist.top_level == ['my_package']
    assert bdist.finalize()
    assert bdist.outname == 'my_package-1.0-py3-none-any.whl'
    assert osp.relpath( bdist.outpath, tmpdir ) == 'build/my_package-1.0-py3-none-any.whl'
    assert osp.exists(bdist.outpath)

    # overwrite existing file
    with dist_binary_wheel(
      pkg_info = pkg_info,
      outdir = out_dir,
      compat = [ ( 'py3', 'none', 'any' ), ],
      gen_name = 'custom' ) as bdist:

      bdist.copytree(
        src = pkg_dir,
        dst = 'my_package' )