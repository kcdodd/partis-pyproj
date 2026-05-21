# Task 5 — `dist_file/dist_binary.py` uncovered paths

**Target file:** `src/pyproj/dist_file/dist_binary.py`  
**Test file:** `tests/test_09_backend.py` or new `test_05c_dist_binary.py`  
**Coverage before:** 77%

## Missing branches

### `finalize` with `metadata_directory` set (lines 244–255)

PEP 517 allows a front-end to call `prepare_metadata_for_build_wheel` first, then
pass the resulting directory as `metadata_directory` to `build_wheel`. The backend
must then include any unrecognized files from that directory in the dist-info.

The existing tests never exercise this path. To test:
1. Build the wheel metadata via `prepare_metadata_for_build_wheel` into a temp dir
2. Add an extra file to that directory (simulating a front-end that wrote something
   the backend doesn't know about)
3. Call `build_wheel` with `metadata_directory=<that dir>`
4. Verify the extra file appears in the resulting wheel's dist-info

The backend test in `test_09_backend.py` already calls `build_wheel`; extend it to
pass `metadata_directory`.

### `dist_binary_editable.copyfile` error paths (lines 431, 434)

`dist_binary_editable` is the editable-install variant of the binary wheel. Its
`copyfile` method (lines 419–452) has two error guards:

- Line 431: source file does not exist → `PathError`
- Line 434: destination already has an entry and `exist_ok=False` → `PathError`

These can be unit-tested by constructing a `dist_binary_editable` in a temp dir
and calling `copyfile` with a nonexistent src, or a duplicate dst.

### `dist_binary_editable.write` (lines 461–476)

The `write` method on the editable variant writes bytes directly to the `whl_root`
filesystem tree instead of into a zip. It is entirely untested. Test:
1. Construct `dist_binary_editable` in a temp dir
2. Call `write('some/path.py', b'content')`
3. Verify the file appears on disk at `whl_root/some/path.py`
4. Verify it appears in `dist.records`

## Note on `dist_binary_editable` construction

`dist_binary_editable` is created by `backend.build_editable` (or the
`dist_binary_editable` context manager imported from `partis.pyproj`). The test for
the editable install in `test_14_editable.py` exercises the full path but doesn't
drill into the low-level write methods. Consider adding targeted unit tests that
construct the class directly.

## Acceptance criteria

- `finalize(metadata_directory=...)` path covered
- `copyfile` raises on missing src and on duplicate dst
- `write` on editable variant covered end-to-end
- `dist_file/dist_binary.py` coverage moves from 77% → 90%+
