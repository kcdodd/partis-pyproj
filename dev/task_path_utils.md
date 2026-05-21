# Task 1 — `path/utils.py` unit tests

**Target file:** `src/pyproj/path/utils.py`  
**Test file:** `tests/test_02_path.py` (add cases here, or a new `test_02b_path_utils.py`)  
**Coverage before:** 63%

## Missing branches

### `_concretize` (lines 38–50)

| Line | Branch | What to test |
|------|--------|--------------|
| 39 | `not comp` | Pass a component list containing an empty string `''` — should be skipped |
| 39 | `comp == curdir` | Pass `['.', 'a']` — the `'.'` should be skipped, result is `['a']` |
| 44 | `return None` | Pass `['a', '..', '..']` — goes up past root, must return `None` |

### `_subdir` (lines 53–68)

| Line | Branch | What to test |
|------|--------|--------------|
| 58 | start non-concretizable | `_subdir(['a', '..', '..'], ['b'])` — start can't be concretized, returns `None` |
| 61 | path non-concretizable | `_subdir(['a'], ['a', '..', '..'])` — path can't be concretized, returns `None` |

### `subdir` (lines 71–97)

| Line | Branch | What to test |
|------|--------|--------------|
| 93 | `check=True` raises | `subdir(PurePath('a/b'), PurePath('c/d'))` — not a subdirectory, must raise `PathError` |
| 95 | `check=False` returns None | Same inputs, `check=False`, must return `None` |

### `file_size_mtime` (lines 100–109)

| Line | Branch | What to test |
|------|--------|--------------|
| 106–108 | `FileNotFoundError` | Call with a path that does not exist — must return `(0, 0, path)` |

### `git_tracked_mtime` / `_git_tracked_mtime` (lines 112–131)

These call `git rev-parse` and `git ls-files` via `check_output`, so they require
either a real git repo context or a mock.

Options:
- **Preferred:** Run inside a real temp git repo (use `tmp_path` fixture + `git init`
  + `git add` + `git commit`). This tests the actual behavior without mocking.
- **Alternative:** `unittest.mock.patch('subprocess.check_output', ...)` if a real
  git repo is too heavyweight.

The `git_tracked_mtime(root=...)` overload (lines 116–122) just `chdir`s and delegates;
a simple test confirming it returns the same result as calling from inside the directory
is sufficient.

## Acceptance criteria

- All five `_concretize` / `_subdir` / `subdir` branches covered
- `file_size_mtime` returns `(0, 0, path)` for missing file
- `git_tracked_mtime` with `root=` argument covered
- `path/utils.py` coverage moves from 63% → 90%+
