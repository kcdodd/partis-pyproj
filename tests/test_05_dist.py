import os
import os.path as osp
import stat
import tempfile
import shutil
import zipfile

from pytest import (
  raises )

from pathlib import (
  Path,
  PurePath,
  PurePosixPath)

from partis.pyproj import (
  PkgInfo,
  dist_base,
  dist_targz,
  dist_zip,
  dist_source_targz,
  dist_source_dummy,
  dist_binary_wheel )

#===============================================================================
def test_dist_base():

  class dist_dummy( dist_base ):
    #-----------------------------------------------------------------------------
    def create_distfile( self ):
      # cause error while opening
      raise NotImplementedError('')

    #-----------------------------------------------------------------------------
    def close_distfile( self ):
      # no error so 'close' will be successful
      pass

    #-----------------------------------------------------------------------------
    def copy_distfile( self ):
      raise NotImplementedError('')

    #-----------------------------------------------------------------------------
    def remove_distfile( self ):
      # no error so 'close' will be successful
      pass

    #-----------------------------------------------------------------------------
    def finalize( self ):
      raise NotImplementedError('')

  dist = dist_dummy('asdasd')

  assert not dist.exists('stuff')

  with raises(NotImplementedError):

    dist.open()


  class dist_dummy2( dist_base ):
    #-----------------------------------------------------------------------------
    def exists( self, dst ):
      return True

    #-----------------------------------------------------------------------------
    def create_distfile( self ):
      pass

    #-----------------------------------------------------------------------------
    def close_distfile( self ):
      pass

    #-----------------------------------------------------------------------------
    def copy_distfile( self ):
      pass

    #-----------------------------------------------------------------------------
    def remove_distfile( self ):
      pass

    #-----------------------------------------------------------------------------
    def finalize( self ):
      pass

  dist = dist_dummy2('asdasd')
  dist.open()

  with raises(ValueError):
    dist.makedirs('stuff')


#===============================================================================
def test_dist_source_dummy():

  with raises( ValueError ):
    dist_source_dummy( pkg_info = None )

  pkg_info = PkgInfo(
    project = dict(
      name = 'my-package',
      version = '1.0' ) )

  dist_source_dummy( pkg_info = pkg_info )

#===============================================================================
def test_dist_targz():

  with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)

    with dist_targz(
      outname = 'asd.tgz',
      outdir = tmpdir ) as dist:

      assert not dist.exists('stuff')

      dist.write('stuff', 'stuff content')

      assert dist.exists('stuff')

      dist.assert_recordable()

      dist.finalize()
      dist.finalized = True

      with raises( ValueError ):
        dist.assert_recordable()

    with raises( ValueError ):
      dist.assert_recordable()

    # should be able to call any number of times
    dist.close_distfile()

#===============================================================================
def test_dist_zip():

  with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)

    with dist_zip(
      outname = 'asd.zip',
      outdir = tmpdir ) as dist:

      assert not dist.exists('stuff')

      dist.write('stuff', 'stuff content')

      assert dist.exists('stuff')

      dist.assert_recordable()

    with raises( ValueError ):
      dist.assert_recordable()

    # should be able to call any number of times
    dist.close_distfile()

#===============================================================================
def test_dist_source():

  with raises( ValueError ):
    dist_source_targz( pkg_info = None )

  with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)

    pkg_dir = tmpdir/'src'/'my_package'
    out_dir = tmpdir/'build'
    mod_file = pkg_dir/'module.py'

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
        src = tmpdir/'src',
        dst = sdist.base_path/'src',
        ignore = shutil.ignore_patterns('nothing') )

      sdist.copyfile(
        src = mod_file,
        dst = sdist.base_path/'src'/'mod.py')

      # NOTE: should not raise error on exact duplicates because the record wouldn't change
      sdist.copyfile(
        src = mod_file,
        dst = sdist.base_path/'src'/'mod.py')

      with open( mod_file, 'w' ) as fp:
        # change file contents to overwrite with actually different file
        fp.write("print('goodbye')")

      with raises( ValueError ):
        # NOTE: should now raise error because the destination is being replaced
        # with different file contents
        sdist.copytree(
          src = tmpdir/'src',
          dst = sdist.base_path/'src')

      with raises( ValueError ):
        # duplicate
        sdist.copyfile(
          src = mod_file,
          dst = sdist.base_path/'src'/'mod.py')

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
        src = tmpdir/'src' ,
        dst = sdist.base_path/'src2'  )

    assert sdist.outname == 'my_package-1.0.tar.gz'
    assert osp.relpath(sdist.outpath, tmpdir) == osp.join('build','my_package-1.0.tar.gz')
    assert osp.exists(sdist.outpath)

    # overwrite existing file
    sdist = dist_source_targz(
      pkg_info = pkg_info,
      outdir = out_dir )

    sdist.open()

    with sdist:

      sdist.copytree(
        src = tmpdir/'src' ,
        dst = sdist.base_path/'src'  )

#===============================================================================
def test_dist_binary_wheel():



  with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)
    pkg_dir = tmpdir/'src'/'my_package'
    out_dir = tmpdir/'build'

    pkg_dir.mkdir(parents=True)

    with open( pkg_dir/'module.py' , 'w' ) as fp:
      fp.write("print('hello')")


    license_file = tmpdir/'license.rst'

    with open(license_file, 'w') as fp:
      fp.write("my license")


    pkg_info = PkgInfo(
      root = tmpdir,
      project = dict(
        name = 'my-package',
        version = '1.0',
        license = { 'file' : 'license.rst' } ) )

    with raises( ValueError ):
      pkg_info_dynamic = PkgInfo(
        project = dict(
          name = 'my-package',
          version = '1.0',
          dynamic = ['dependencies'] ) )

    with raises( ValueError ):
      dist_binary_wheel( pkg_info = None )

    # with raises( ValueError ):
    #   dist_binary_wheel( pkg_info = pkg_info_dynamic )


    dist_binary_wheel( pkg_info = pkg_info )


    with dist_binary_wheel(
      pkg_info = pkg_info,
      outdir = out_dir,
      compat = [ ( 'py3', 'none', 'any' ), ],
      gen_name = 'custom' ) as bdist:

      for k in bdist.named_dirs.keys():

        bdist.copytree(
          src = pkg_dir,
          dst = bdist.named_dirs[k].joinpath('my_package'))

    #assert bdist.top_level == ['my_package']
    assert bdist.finalize()
    assert bdist.outname == 'my_package-1.0-py3-none-any.whl'
    assert osp.relpath(bdist.outpath, tmpdir) == osp.join('build','my_package-1.0-py3-none-any.whl')
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

#===============================================================================
# dist_zip additional branch coverage
#===============================================================================

def test_dist_zip_copy_overwrite(tmp_path):
  # copy_distfile: outpath already exists → unlink before copying (line 112)
  with dist_zip(outname='over.zip', outdir=tmp_path) as d:
    d.write('first.txt', b'first')

  assert (tmp_path / 'over.zip').exists()

  with dist_zip(outname='over.zip', outdir=tmp_path) as d:
    d.write('second.txt', b'second')

  with zipfile.ZipFile(tmp_path / 'over.zip') as zf:
    assert 'second.txt' in zf.namelist()
    assert 'first.txt' not in zf.namelist()

def test_dist_zip_remove_no_tmppath(tmp_path):
  # remove_distfile: _tmp_path is falsy (never opened) → early return, no error
  d = dist_zip(outname='never.zip', outdir=tmp_path)
  d.remove_distfile()  # must not raise

def test_dist_zip_write_duplicate_no_record(tmp_path):
  # write with record=False, same dst twice → ValueError (line 154)
  with dist_zip(outname='dup.zip', outdir=tmp_path) as d:
    d.write('a/b.txt', b'first', record=False)
    with raises(ValueError, match='Overwriting destination'):
      d.write('a/b.txt', b'second', record=False)

def test_dist_zip_write_link(tmp_path):
  # write_link happy path: entry has symlink bit, data is encoded target
  with dist_zip(outname='links.zip', outdir=tmp_path) as d:
    d.write_link('link/target.py', '../real/target.py')

  with zipfile.ZipFile(tmp_path / 'links.zip') as zf:
    info = zf.getinfo('link/target.py')
    assert (info.external_attr >> 16) & 0xF000 == stat.S_IFLNK
    assert zf.read('link/target.py') == b'../real/target.py'

def test_dist_zip_write_link_dedup(tmp_path):
  # write_link record=True, identical link twice → second is a no-op (rec is None)
  with dist_zip(outname='dedup.zip', outdir=tmp_path) as d:
    d.write_link('a.py', '../b.py')
    d.write_link('a.py', '../b.py')  # must not raise

  with zipfile.ZipFile(tmp_path / 'dedup.zip') as zf:
    assert zf.namelist().count('a.py') == 1

def test_dist_zip_write_link_overwrite_guard(tmp_path):
  # write_link record=False, exist_ok=False, dst already written → ValueError (line 192)
  with dist_zip(outname='guard.zip', outdir=tmp_path) as d:
    d.write_link('a.py', '../b.py')
    with raises(ValueError, match='Overwriting destination'):
      d.write_link('a.py', '../c.py', record=False, exist_ok=False)
