"""
Tests for dist_binary_wheel and dist_binary_editable covering:
  - finalize: idempotency (record_hash already set → early return)
  - finalize: metadata_directory path (RECORD skip, exists skip, copyfile)
  - dist_binary_editable: lifecycle (create_distfile creates whl_root; close/copy/remove are no-ops)
  - dist_binary_editable: write() and exists()
  - dist_binary_editable: copyfile() happy path (creates symlink)
  - dist_binary_editable: copyfile() error cases (missing src, duplicate without exist_ok)
"""
import zipfile
import pytest

from partis.pyproj import PkgInfo
from partis.pyproj.dist_file.dist_binary import dist_binary_wheel, dist_binary_editable
from partis.pyproj.path import PathError


def _pkg_info():
  return PkgInfo(project=dict(name='test-pkg', version='0.1'))

def _editable(tmp_path, whl_root):
  return dist_binary_editable(
    root=tmp_path,
    pptoml_checksum=('deadbeef', 8),
    whl_root=whl_root,
    pkg_info=_pkg_info(),
    outdir=tmp_path)

#===============================================================================
# dist_binary_wheel.finalize — idempotency (record_hash already set → early return)
#===============================================================================

def test_finalize_idempotent(tmp_path):
  with dist_binary_wheel(pkg_info=_pkg_info(), outdir=tmp_path) as d:
    hash1 = d.finalize()
    hash2 = d.finalize()  # record_hash already set → early return
  assert hash1 is not None
  assert hash1 == hash2

#===============================================================================
# dist_binary_wheel.finalize — metadata_directory
#===============================================================================

def test_finalize_metadata_directory(tmp_path):
  meta_dir = tmp_path / 'meta'
  meta_dir.mkdir()
  (meta_dir / 'RECORD').write_bytes(b'ignored')        # always skipped (line 236)
  (meta_dir / 'WHEEL').write_bytes(b'wheel-override')  # exists in zip → skipped (line 241)
  (meta_dir / 'EXTRA.txt').write_bytes(b'extra-data')  # new → copied into dist_info (line 244)

  out_dir = tmp_path / 'out'
  with dist_binary_wheel(pkg_info=_pkg_info(), outdir=out_dir) as d:
    d.finalize(metadata_directory=str(meta_dir))
    # context exit calls finalize() again → record_hash already set → early return (line 200)

  whl = next(out_dir.glob('*.whl'))
  with zipfile.ZipFile(whl) as zf:
    names = zf.namelist()

  assert any('EXTRA.txt' in n for n in names)
  # RECORD from meta_dir was skipped; only the standard dist-info RECORD is present
  assert sum(1 for n in names if n.endswith('/RECORD')) == 1

#===============================================================================
# dist_binary_editable — lifecycle
#===============================================================================

def test_editable_lifecycle(tmp_path):
  # create_distfile creates the whl_root; close/copy/remove are all no-ops
  whl_root = tmp_path / 'whl_root'
  d = _editable(tmp_path, whl_root)

  d.open()
  assert whl_root.is_dir()

  d.close(finalize=False)

#===============================================================================
# dist_binary_editable — write() and exists()
#===============================================================================

def test_editable_write_exists(tmp_path):
  whl_root = tmp_path / 'whl_root'
  d = _editable(tmp_path, whl_root)
  d.open()

  assert not d.exists('hello.txt')
  d.write('hello.txt', b'hello world')
  assert d.exists('hello.txt')
  assert (whl_root / 'hello.txt').read_bytes() == b'hello world'

  # nested path: parent dirs created on demand
  d.write('sub/pkg/mod.py', b'# mod')
  assert (whl_root / 'sub' / 'pkg' / 'mod.py').exists()

  d.close(finalize=False)

#===============================================================================
# dist_binary_editable — copyfile() happy path (creates a symlink)
#===============================================================================

def test_editable_copyfile(tmp_path):
  whl_root = tmp_path / 'whl_root'
  src_file = tmp_path / 'real.py'
  src_file.write_text('x = 1')

  d = _editable(tmp_path, whl_root)
  d.open()

  d.copyfile(src=src_file, dst='real.py')
  link = whl_root / 'real.py'
  assert link.is_symlink()
  assert link.resolve() == src_file.resolve()

  d.close(finalize=False)

#===============================================================================
# dist_binary_editable — copyfile() error cases
#===============================================================================

def test_editable_copyfile_missing_src(tmp_path):
  whl_root = tmp_path / 'whl_root'
  d = _editable(tmp_path, whl_root)
  d.open()

  with pytest.raises(PathError, match='Source file not found'):
    d.copyfile(src=tmp_path / 'ghost.py', dst='ghost.py')

  d.close(finalize=False)

def test_editable_copyfile_duplicate(tmp_path):
  whl_root = tmp_path / 'whl_root'
  src_file = tmp_path / 'mod.py'
  src_file.write_text('x = 1')

  d = _editable(tmp_path, whl_root)
  d.open()

  d.copyfile(src=src_file, dst='mod.py')
  with pytest.raises(PathError, match='Build file already has entry'):
    d.copyfile(src=src_file, dst='mod.py')  # exist_ok=False by default

  d.close(finalize=False)
