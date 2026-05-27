# Test Phase 2 Plan

**Goal:** Push overall coverage from 95% toward 100% by targeting the uncovered branches
in the 12 files that still have gaps. All work adds to existing test files unless a new
file is the cleaner fit.

---

## Current gaps (by file)

| File | Cov | Miss | Priority |
|---|---|---|---|
| `builder/cmake.py` | 75% | 3 | medium |
| `builder/meson.py` | 78% | 3 | medium |
| `path/scandir.py` | 82% | 16 | high |
| `dist_file/dist_targz.py` | 84% | 7 | high |
| `dist_file/dist_copy.py` | 85% | 13 | high |
| `load_module.py` | 85% | 11 | high |
| `template.py` | 90% | 9 | high |
| `pyproj.py` | 91% | 14 | high |
| `dist_file/dist_base.py` | 91% | 10 | high |
| `backend.py` | 92% | 4 | medium |
| `validate.py` | 95% | 23 | medium |
| `path/pattern.py` | 96% | 6 | low |

---

## Work items

### 1. `tests/test_18_scandir.py` — NEW FILE

`path/scandir.py` has no dedicated test file yet and accounts for 16 missing lines.

- **gitignore integration**: call `scandir_recursive()` on a `tmp_path` tree containing a
  `.gitignore` file; verify ignored paths are excluded. Covers lines 129, 216–219.
- **`DirInfo.get()` with list path**: call `.get(['subdir', 'file.py'])` instead of a
  `PurePath`. Covers line 47.
- **`DirInfo.get()` with non-existent path**: request a name that doesn't exist in the
  scanned tree; verify `None` or appropriate return. Covers lines 55, 63, 74.
- **`DirInfo.__str__()`**: call `str()` on a `DirInfo` instance. Covers lines 161–167.
- **`.glob()` with `exclude=None`** and **`exclude=PathFilter`** (single object, not
  tuple). Covers lines 101, 103.
- **OSError on stat / scandir**: mock `os.scandir` or `entry.stat` to raise `OSError`;
  verify graceful handling. Covers lines 222, 225.

---

### 2. `tests/test_05_dist.py` — extend

#### `dist_targz` edge cases (7 missing lines)

- **`copy_distfile()` before `create_distfile()`**: call copy without creating first;
  expect early-return / no error. Covers line 110.
- **`remove_distfile()` before create**: same pattern. Covers line 123.
- **Duplicate `write()` with `record=False`**: write same dst twice; expect overwrite
  error on second call. Covers lines 154, 156.
- **Duplicate `write_link()` same dst**: call twice; first succeeds, second is a no-op
  (rec is None branch). Covers lines 188–190.
- **`write_link()` with `record=False` + duplicate**: expect overwrite error. Covers
  lines 192, 194.

#### `dist_copy` edge cases (13 missing lines)

- **Empty glob match warning**: pass an include glob pattern that matches no files; verify
  warning is logged. Covers lines 78–80.
- **`rematch` that doesn't match filename**: use `rematch=r"\.pyx$"` on `.py` files;
  file should be skipped. Covers lines 97–99.
- **Invalid `replace` format string**: use `replace="{99}"` with a `rematch` that captures
  one group; expect `ValidationError`. Covers lines 113–117.
- **Duplicate `(src, dst)` pair**: configure two copy operations that produce identical
  destination paths; expect the duplicate to be skipped (line 167) or raise. Covers
  lines 167, 169.
- **Exception in `scanned.get()`**: mock `DirInfo.get` to raise; verify propagation.
  Covers lines 50, 52–53.

---

### 3. `tests/test_06_load_module.py` — extend

Only one test exists today (25 lines). Add:

- **`ImportError` for unknown stdlib reference**: try to load
  `"nonexistent_stdlib_module:func"`; expect `EntryPointError`. Covers lines 108–109.
- **Re-raised `EntryPointError` from `load_module()`**: mock `load_module` to raise
  `EntryPointError`; verify it propagates cleanly. Covers lines 118–119.
- **Generic exception from `load_module()`**: mock to raise `RuntimeError`; verify
  wrapped in `EntryPointError`. Covers lines 121–122.
- **`EntryPoint.__call__()` raises `ValidationError`**: mock the resolved callable to
  raise `ValidationError`; verify it's caught and re-raised. Covers line 188.
- **`module_name_from_path()` at project root**: pass a path equal to the root; verify
  empty-name handling. Covers lines 42, 44–45.

---

### 4. `tests/test_03_template.py` / `tests/test_13_template_extra.py` — extend

- **`Template.substitute()` with no namespace, only kwargs**:
  `Template("${X}").substitute(X=10)`. Covers line 61.
- **Both namespace and kwargs**: `Template("${X}").substitute({}, Y=10)`; expect
  `TemplateError`. Covers line 64.
- **Non-`Namespace` dict**: `Template("${X}").substitute({'X': 10})`. Covers line 67.
- **`Namespace(dirs=single_Path)`**: pass a single `Path` rather than a list. Covers
  line 108.
- **`iter(namespace)` and `len(namespace)`**: call `__iter__` and `__len__` directly.
  Covers lines 116, 120.
- **`Namespace` with `root=None` path substitution**: access a path-valued key when root
  is `None`; verify behaviour. Covers lines 147–148.
- **Nested attribute on scalar**: `namespace['X.Y']` where `X` is an int; expect
  `NamespaceError`. Covers line 196.

---

### 5. `tests/test_08_pyproj.py` — extend

- **Missing `tool` key**: load a `pyproject.toml` that has no `[tool]` table; expect
  `ValidationError`. Covers line 109.
- **Missing `tool.pyproj` key**: `[tool]` present but no `[tool.pyproj]`; expect
  `ValidationError`. Covers line 113.
- **Git subprocess failure**: patch `subprocess.check_output` to raise
  `subprocess.CalledProcessError`; verify `RuntimeWarning` is emitted. Covers lines
  181–184.
- **Deprecated `meson` property — validation error**: access `.meson` on a `PyProjBase`
  that has multiple or non-meson targets; expect `ValidationError`. Covers lines 259–270.

---

### 6. `tests/test_05_dist.py` / `tests/test_09_backend.py` — extend

#### `dist_base` (10 missing lines)

- **`copytree()` with symlink in source tree**: create a `tmp_path` tree containing a
  symlink; verify `write_link()` is called and the link is recorded. Covers lines 298,
  306.
- **`copytree()` with ignored entries**: use an ignore pattern that matches a file in the
  tree; verify the debug log is emitted. Covers line 282.
- **`record()` with `exist_ok=True` on duplicate**: call `record()` twice with the same
  dst; second call should log and not raise. Covers line 405.
- **`write()` and `write_link()` with `record=True`**: exercise the `record=True`
  conditional. Covers lines 146–147, 170, 172–176.

#### `backend.py` (4 missing lines)

- **`backend_init(init_logging=False)`**: verify logging setup is skipped. Covers line 81.
- **`_run_editable_cmd()` missing `bin/` dir**: call the editable rebuild helper against a
  venv directory that has neither `bin` nor `Scripts`; expect `FileNotFoundError`.
  Covers lines 401, 416, 421.

---

### 7. `tests/test_00_validate.py` — extend

23 missing lines, mostly edge-cases in descriptor and collection protocols:

- **`_ValidDictAttr.__get__()` with `obj=None`**: access the descriptor from the class,
  not an instance; verify descriptor itself is returned. Covers line 726.
- **`_ValidDictAttr.__delete__()`**: call `del` on an attribute backed by the descriptor.
  Covers lines 737–738.
- **`_ValidDictAttr.__repr__()`**: call `repr()` on the descriptor. Covers line 742.
- **`valid_dict.update()`**: call `.update({key: val})` on a `valid_dict` instance with a
  validator. Covers lines 1007–1008.
- **`valid_dict.popitem()`**: call `.popitem()`. Covers lines 1028–1030.
- **`valid_dict.__setitem__()` with `key_valid`**: assign through `[]` when a key
  validator is set. Covers line 1046.
- **`valid_dict.__delitem__()` with `key_valid`**: delete through `[]`. Covers line 1056.
- **`valid_list.extend()` with `value_valid`**: call `.extend([...])`. Covers lines
  1121–1123.
- **`valid_list.__setitem__()` with `value_valid`**: assign through `[]`. Covers lines
  1130–1131.
- **`fmt_validator()` with callable lacking `__qualname__`**: pass a C-level callable or
  a `functools.partial`; verify name resolution fallback. Covers lines 344–348, 351.
- **Sequence-not-list/tuple validator definition error**: pass a `tuple` of validators
  where a `list` is required; expect `ValidDefinitionError`. Covers lines 123, 280.

---

### 8. `tests/test_15_builder.py` — extend

- **cmake missing executable**: mock `shutil.which('cmake')` to return `None`; expect
  `ValueError`. Covers `cmake.py` lines 47, 50.
- **meson missing executable**: same pattern for meson/ninja. Covers `meson.py` lines 45,
  48.
- **`build_clean=False` skips setup** (cmake and meson): call with a pre-existing
  `build_dir` and `build_clean=False`; verify setup args list is empty / setup is not
  called. Covers `cmake.py` line 55, `meson.py` line 55.

---

### 9. `path/pattern.py` — low priority, defer

Lines 202–203 (`finalize()` no-op), 247 (`GList.__str__` referencing undefined `_regex`,
possible latent bug), 354 (empty segment), 556 (`GALLDIR` `/**` suffix), 564 (chrset),
571 (defensive assertion). Address if the above items don't already drag them in via
integration paths; otherwise track as a separate task.

---

## Verification

After implementation, run:

```sh
# build from source first (required)
nox -s prepare

# run full test suite with coverage
nox -s test-3.11

# combine and report
nox -s report
```

Target: overall coverage ≥ 98%; every file in the gap list at ≥ 95%.

To run a single new test file quickly without nox isolation:

```sh
pytest tests/test_18_scandir.py -x -v
```
