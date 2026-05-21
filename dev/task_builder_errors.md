# Task 3 — `builder/builder.py` error paths

**Target file:** `src/pyproj/builder/builder.py`  
**Test file:** `tests/test_08_pyproj.py` or new `test_15_builder.py`  
**Coverage before:** 71%

## Missing branches

### `pyexe = osp.realpath(pyexe)` try/except (lines 38–41)

Module-level code; the `except Exception: ...` is the case where `realpath` fails.
This is effectively untestable without monkeypatching `os.path.realpath` to raise, and
the consequence is silent (falls back to the original `sys.executable`). Consider
marking `pragma: no cover` if it is not worth mocking.

### Exclusive target group logic (lines 127–142, 150)

`tool.pyproj.targets` supports an `exclusive` key so only one target per group runs.
The uncovered branches are:

- **No enabled target in group** (line 142): multiple targets in the same `exclusive`
  group, all disabled → should raise `ValidationError`.
- **Second target in group skipped** (line 150): two targets in same group, both
  enabled → first runs, second is skipped with a warning.

Test approach: use a minimal fake project (`tests/pkg_base` style) with a target using
`partis.pyproj.builder:process` (already tested) and set `enabled = false` / duplicate
`exclusive` keys in a temp `pyproject.toml`.

### Build-dirty / incremental detection (lines 205–232)

This is the logic that decides whether to clean `build_dir` before re-building:

- **Status file exists, content unchanged, `build_clean=False`**: should *not* clean.
- **Status file exists, content changed, `build_clean=False`**: should clean and log a diff.
- **`build_dir` non-empty, `build_clean=True`** but status file missing: should raise
  `ValidPathError` ("not empty, please remove manually").

All three cases require a temp directory that looks like a previous build. Easiest
approach: create the `build_dir` and `.pyproj_status` file manually in `tmp_path`
before invoking the builder.

### `CalledProcessError` output formatter (lines 399–444)

When a subprocess target exits non-zero, the builder extracts lines around "error"
patterns and the last N lines of stdout. The entire formatter block (399–444) is
uncovered.

Test approach: use `partis.pyproj.builder:process` with a command guaranteed to fail
(e.g. `python -c "import sys; print('ERROR: something bad'); sys.exit(1)"`).
Check that the resulting `BuildCommandError` message contains the expected lines.

## Acceptance criteria

- Exclusive group "no enabled target" raises `ValidationError`
- Exclusive group "second target skipped" emits a warning
- All three build-dirty branches covered
- `CalledProcessError` formatter produces output containing relevant error lines
- `builder/builder.py` coverage moves from 71% → 85%+
- Lines 38–41 either covered or marked `pragma: no cover`
