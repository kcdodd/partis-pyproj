# Task 7 — `cli/build_pyproj.py` prep and rebuild commands

**Target file:** `src/pyproj/cli/build_pyproj.py`  
**Test file:** `tests/test_14_editable.py` (extend) or new `test_15_cli_rebuild.py`  
**Coverage before:** 40%

This is the largest gap and the hardest to test. The `rebuild` command requires a
fully initialized editable installation (a staging directory with a `build_venv` and
a prior wheel). Tackle after tasks 1–6.

## What's untested

### `_prep_pyproj` (lines 35–45)

Calls `backend_init(editable=True)`, then `pyproj.dist_prep()` and
`pyproj.dist_binary_prep()`. These are the "prepare" steps that run before a binary
distribution is copied.

### `_rebuild_pyproj` (lines 74–131)

The full rebuild flow:
- Line 84–86: project has no build targets → prints message and exits 0
- Line 91–93: editable root doesn't exist → prints message and exits 1
- Lines 95–131: full rebuild — runs `prep` in `build_venv`, removes old wheel dir,
  re-builds wheel into editable staging dir

## Test strategy

### `_prep_pyproj` — low-hanging fruit

This function does not require an editable environment. Test it against `tests/pkg_min`
or `tests/pkg_base` (already used by other tests):

```python
from partis.pyproj.cli.build_pyproj import _prep_pyproj
_prep_pyproj(path=Path('tests/pkg_min'))
# should complete without error for a pure-python package with no build targets
```

### `_rebuild_pyproj` — "no targets" branch (easiest)

Use a pure-python package (no `tool.pyproj.targets`). Call `_rebuild_pyproj` and
expect it to print "Project has no build targets." and call `sys.exit(0)`. Use
`pytest.raises(SystemExit)` to catch the exit.

### `_rebuild_pyproj` — "editable root not found" branch

Pass a `root` with build targets but an `editable_root` that does not exist:

```python
with pytest.raises(SystemExit) as exc:
    _rebuild_pyproj(root=..., editable_root=Path('/nonexistent/path'))
assert exc.value.code == 1
```

### `_rebuild_pyproj` — full rebuild

This requires:
1. A test package with at least one build target (e.g. `tests/pkg_meson_1` or a
   simple `process` target that copies a file)
2. A pre-existing editable staging directory at `pyproj.editable_root` with a
   `build_venv` that has `partis-pyproj` installed

The existing `test_14_editable.py` may already set up this environment. If so, run
`_rebuild_pyproj` against it and verify the wheel directory is rebuilt.

If the editable environment is too expensive to set up in CI for unit tests, this
branch could be covered by an integration test that only runs locally (mark with
`pytest.mark.slow` or similar), or rely on the CI's editable test implicitly covering
it via `partis-pyproj rebuild` in a nox session.

## Acceptance criteria

- `_prep_pyproj` covered for a pure-python package
- "no targets" branch covered (exits 0)
- "editable root not found" branch covered (exits 1)
- Full rebuild covered or explicitly deferred with a note
- `cli/build_pyproj.py` coverage moves from 40% → 70%+
