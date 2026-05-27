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

#===============================================================================
# dist_targz additional branch coverage
#===============================================================================

def test_dist_targz_copy_before_create(tmp_path):
  # copy_distfile with no _tmp_path → early return, no error (line 110)
  d = dist_targz(outname='never.tgz', outdir=tmp_path)
  d.copy_distfile()  # must not raise

def test_dist_targz_remove_before_create(tmp_path):
  # remove_distfile with no _tmp_path → early return, no error (line 123)
  d = dist_targz(outname='never.tgz', outdir=tmp_path)
  d.remove_distfile()  # must not raise

def test_dist_targz_write_duplicate_no_record(tmp_path):
  # write with record=False, same dst twice, exist_ok=False → ValueError (lines 154, 156)
  with dist_targz(outname='dup.tgz', outdir=tmp_path) as d:
    d.write('a/b.txt', b'first', record=False)
    with raises(ValueError, match='Overwriting destination'):
      d.write('a/b.txt', b'second', record=False)

def test_dist_targz_write_link_dedup(tmp_path):
  # write_link record=True, identical link twice → second is a no-op (lines 188-190)
  with dist_targz(outname='dedup.tgz', outdir=tmp_path) as d:
    d.write_link('a.py', '../b.py')
    d.write_link('a.py', '../b.py')  # must not raise

def test_dist_targz_write_link_no_record_duplicate(tmp_path):
  # write_link record=False, exist_ok=False, dst already written → ValueError (lines 192, 194)
  with dist_targz(outname='guard.tgz', outdir=tmp_path) as d:
    d.write_link('a.py', '../b.py')
    with raises(ValueError, match='Overwriting destination'):
      d.write_link('a.py', '../c.py', record=False, exist_ok=False)

#===============================================================================
# dist_base additional branch coverage
#===============================================================================

def test_dist_base_copytree_with_symlink(tmp_path):
  # copytree with a symlink in the source tree → write_link is called (lines 298, 306)
  src = tmp_path / 'src'
  src.mkdir()
  real_file = src / 'real.txt'
  real_file.write_text('hello')
  link_file = src / 'link.txt'
  link_file.symlink_to('real.txt')

  out = tmp_path / 'out'
  out.mkdir()

  with dist_targz(outname='sym.tgz', outdir=out) as d:
    d.copytree(src=src, dst='pkg')

  import tarfile as _tarfile
  with _tarfile.open(out / 'sym.tgz') as tf:
    members = {m.name: m for m in tf.getmembers()}
    assert 'pkg/link.txt' in members
    assert members['pkg/link.txt'].issym()

def test_dist_base_copytree_ignore_logs_debug(tmp_path, caplog):
  # copytree with ignore callable returning names → debug log emitted (line 282)
  import logging as _logging
  src = tmp_path / 'src'
  src.mkdir()
  (src / 'keep.py').write_text('keep')
  (src / 'skip.py').write_text('skip')

  out = tmp_path / 'out'
  out.mkdir()

  with _logging.getLogger('dist_targz').propagate and caplog.at_level(_logging.DEBUG, logger='dist_targz'):
    with dist_targz(outname='ign.tgz', outdir=out) as d:
      with caplog.at_level(_logging.DEBUG):
        d.copytree(src=src, dst='pkg', ignore=lambda path, names: ['skip.py'])

  assert any('ignoring' in r.message for r in caplog.records)

def test_dist_base_record_exist_ok_overwrites(tmp_path):
  # record() with exist_ok=True on duplicate key with different data → logs overwrite (line 405)
  out = tmp_path / 'out'
  out.mkdir()

  with dist_targz(outname='rec.tgz', outdir=out) as d:
    d.record('file.txt', b'first data', exist_ok=False)
    # second call with different data and exist_ok=True should log overwrite, not raise
    d.record('file.txt', b'different data', exist_ok=True)

def test_dist_base_write_with_record(tmp_path):
  # write() with record=True exercises the record path (lines 146-147)
  out = tmp_path / 'out'
  out.mkdir()

  with dist_targz(outname='wrec.tgz', outdir=out) as d:
    d.write('myfile.txt', b'content', record=True)
    assert 'myfile.txt' in {str(k) for k in d.records}

def test_dist_base_write_link_with_record(tmp_path):
  # write_link() with record=True exercises the record path (lines 170, 172-176)
  out = tmp_path / 'out'
  out.mkdir()

  with dist_targz(outname='wlrec.tgz', outdir=out) as d:
    d.write_link('mylink.py', '../real.py', record=True)
    assert 'mylink.py' in {str(k) for k in d.records}

#===============================================================================
# dist_copy (dist_iter) additional branch coverage
#===============================================================================

import logging as _logging
from unittest.mock import patch, MagicMock
from partis.pyproj.dist_file.dist_copy import dist_iter
from partis.pyproj.validate import ValidationError
from partis.pyproj.pptoml import PyprojDistCopy
from pathlib import PurePosixPath as _PurePosixPath

def test_dist_iter_empty_glob_warns(tmp_path, caplog):
  # glob pattern matches no files → WARNING logged (lines 78-80)
  src = tmp_path / 'source'
  src.mkdir()
  (src / 'hello.py').write_text('x')

  copy_item = PyprojDistCopy({
    'src': _PurePosixPath('source'),
    'dst': _PurePosixPath('dest'),
    'include': [{'glob': '**/*.pyx'}],
  })

  with caplog.at_level(_logging.WARNING):
    results = list(dist_iter(
      copy_items=[copy_item],
      ignore=[],
      root=tmp_path,
      logger=_logging.getLogger('test_dist_iter'),
    ))

  assert results == []
  assert any('Copy pattern did not yield any files' in r.message for r in caplog.records)

def test_dist_iter_rematch_skips_non_matching(tmp_path):
  # rematch that doesn't match filename → file silently skipped (lines 97-99)
  src = tmp_path / 'source'
  src.mkdir()
  (src / 'hello.py').write_text('x')

  copy_item = PyprojDistCopy({
    'src': _PurePosixPath('source'),
    'dst': _PurePosixPath('dest'),
    'include': [{'glob': '**/*.py', 'rematch': r'\.pyx$'}],
  })

  results = list(dist_iter(
    copy_items=[copy_item],
    ignore=[],
    root=tmp_path,
    logger=_logging.getLogger('test_dist_iter'),
  ))

  assert results == []

def test_dist_iter_invalid_replace_raises(tmp_path):
  # replace format string references non-existent group → ValidationError (lines 113-117)
  src = tmp_path / 'source'
  src.mkdir()
  (src / 'hello.py').write_text('x')

  copy_item = PyprojDistCopy({
    'src': _PurePosixPath('source'),
    'dst': _PurePosixPath('dest'),
    'include': [{'glob': '**/*.py', 'rematch': r'(hello)\.py', 'replace': '{99}'}],
  })

  with raises(ValidationError):
    list(dist_iter(
      copy_items=[copy_item],
      ignore=[],
      root=tmp_path,
      logger=_logging.getLogger('test_dist_iter'),
    ))

def test_dist_iter_duplicate_src_dst_skipped(tmp_path, monkeypatch):
  # two copy operations producing the same (src, dst) → duplicate skipped (lines 167, 169)
  from partis.pyproj.dist_file.dist_copy import dist_copy

  src = tmp_path / 'source'
  src.mkdir()
  (src / 'hello.py').write_text('x')

  copy_items = [
    PyprojDistCopy({'src': _PurePosixPath('source/hello.py'), 'dst': _PurePosixPath('dest/hello.py')}),
    PyprojDistCopy({'src': _PurePosixPath('source/hello.py'), 'dst': _PurePosixPath('dest/hello.py')}),
  ]

  out = tmp_path / 'out'
  out.mkdir()

  monkeypatch.chdir(tmp_path)

  with dist_targz(outname='dup.tgz', outdir=out) as d:
    dist_copy(
      base_path=_PurePosixPath('.'),
      copy_items=copy_items,
      ignore=[],
      dist=d,
      root=tmp_path,
      logger=_logging.getLogger('test_dist_copy'),
    )

  # file should appear exactly once
  import tarfile as _tarfile
  with _tarfile.open(out / 'dup.tgz') as tf:
    names = tf.getnames()
  assert names.count('dest/hello.py') == 1

def test_dist_iter_scanned_get_exception_propagates(tmp_path):
  # DirInfo.get raises RuntimeError → error logged and re-raised (lines 50, 52-53)
  from partis.pyproj.path.scandir import DirInfo

  src = tmp_path / 'source'
  src.mkdir()

  copy_item = PyprojDistCopy({
    'src': _PurePosixPath('source'),
    'dst': _PurePosixPath('dest'),
  })

  with patch.object(DirInfo, 'get', side_effect=RuntimeError('boom')):
    with raises(RuntimeError, match='boom'):
      list(dist_iter(
        copy_items=[copy_item],
        ignore=[],
        root=tmp_path,
        logger=_logging.getLogger('test_dist_iter'),
      ))
