# Task 4 — `dist_file/dist_zip.py` symlink and overwrite branches

**Target file:** `src/pyproj/dist_file/dist_zip.py`  
**Test file:** `tests/test_05_dist.py` or new `test_05b_dist_zip.py`  
**Coverage before:** 74%

## Missing branches

### `copy_distfile` overwrite branch (line 110)

When the destination file already exists, `copy_distfile` unlinks it before copying.
The existing tests never create a pre-existing file at `outpath`. Add a test that:
1. Builds a dist zip to `outpath`
2. Calls `copy_distfile` again (same outpath)
3. Verifies the file is replaced, not an error

### `remove_distfile` early return (line 119)

`remove_distfile` returns immediately if `self._tmp_path` is falsy. This state occurs
when the context manager is entered but the output file was never written (e.g. the
dist was created with an empty `outdir` or before `__enter__`). Trigger by calling
`remove_distfile` on a freshly constructed (but not yet opened) instance.

### `write` with `exist_ok=False` and duplicate dst (line 154)

The `elif not exist_ok and self.exists(dst)` branch raises `ValueError` when writing
a second file to the same destination path without `record=True` (which would deduplicate).
Test:
```python
dist.write('a/b.txt', b'first',  record=False)
dist.write('a/b.txt', b'second', record=False)  # should raise ValueError
```

### `write_link` (lines 173–197) — entirely untested

`write_link` writes a symlink entry into the zip (used for source distributions that
preserve symlinks). The whole method is uncovered. Test:
```python
dist.write_link('link/target.py', '../real/target.py')
# verify the zip contains a symlink entry at 'link/target.py'
# pointing to '../real/target.py'
```

Also test the `exist_ok=False` overwrite guard (line 190) and the deduplication path
when `record=True` and an identical link already exists (line 186, `rec is None`).

## How to open a dist_zip for testing

Look at how `dist_source` or `dist_binary_wheel` are constructed in the existing
`test_05_dist.py` — `dist_zip` is the common base and can be instantiated directly
with a temp path for unit testing the low-level write methods.

## Acceptance criteria

- `copy_distfile` overwrite branch covered
- `remove_distfile` early return covered  
- `write` duplicate-without-record raises `ValueError`
- `write_link` happy path covered
- `write_link` overwrite guard covered
- `dist_file/dist_zip.py` coverage moves from 74% → 90%+
