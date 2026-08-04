# Ultrareview Report — `feat/review` → `master`

**Scope:** 135 files changed, 17,429 insertions
**Findings:** 9 (4 normal, 5 nit)

---

## Summary

| # | Severity | File | Issue |
|---|---|---|---|
| 1 | normal | `src/pyproj/builder/download.py:144-148` | `symlink_to` fails on editable rebuild |
| 2 | normal | `src/pyproj/backend.py:329-340` | Editable install dependency lookup not PEP 503 normalized |
| 3 | normal | `docs/conf.py:102-109` | Hardcoded developer-local paths and wrong project name |
| 4 | normal | `pyproject.toml:31-35` | `requires-python` floor inconsistent with code/CI |
| 5 | nit | `src/pyproj/dist_file/dist_copy.py:82` | `dist_iter` inner loop shadows outer index |
| 6 | nit | `pyproject.toml:60-67` | `build-system.requires` pins old packaging/tomli |
| 7 | nit | `src/pyproj/dist_file/dist_binary.py:444-467` | `dist_binary_editable.write` LSP signature mismatch |
| 8 | nit | `src/pyproj/dist_file/dist_binary.py:227-244` | `finalize` non-recursive metadata_directory iteration |
| 9 | nit | `pkgaux/utils.py:110-130` | `clear_pip_cache` silent no-op |

---

## Normal severity

### 1. `download` builder: unconditional `symlink_to` fails on rebuild

- **File:** `src/pyproj/builder/download.py:144-148`
- **ID:** `bug_016`

The `download` builder unconditionally calls `out_file.symlink_to(cache_file)` at `download.py:147` after both the cache-hit and cache-miss branches. On a second editable rebuild (where `build_clean=False` is now the default per the v0.2.2 release notes), `out_file` already exists as a symlink from the previous run and `Path.symlink_to` raises `FileExistsError`, breaking incremental rebuilds for any target that uses `partis.pyproj.builder:download`. Fix by calling `out_file.unlink(missing_ok=True)` (or checking `out_file.is_symlink()`) before `symlink_to`.

#### What the bug is

`src/pyproj/builder/download.py` ends both the cache-hit branch (which only logs "Using cache file") and the cache-miss branch (which downloads to a tmp file and replaces `cache_file`) by unconditionally executing:

```python
out_file.symlink_to(cache_file)
```

`Path.symlink_to` has no `missing_ok` parameter; if `out_file` already exists (even as a symlink pointing at the same target), Python raises `FileExistsError: [Errno 17]`.

#### Why this fires in the editable-rebuild path

In `builder.py:203`, the builder computes:

```python
build_clean = not self.editable or target.build_clean
```

For editable installs (`self.editable=True`) and the v0.2.2 default `target.build_clean=False`, this evaluates to `False`. Then in `builder.py:209-216`, when the `.pyproj_status` file already exists and its content matches (same commit, same environment), the `build_dir` is *not* cleaned. The symlink from the previous run survives at `build_dir/filename`, and the next call to `download` immediately raises.

Non-editable builds set `build_clean=True`, so `rmtree(build_dir)` runs and the symlink is gone — that path is unaffected. The bug is specific to the editable rebuild workflow that v0.2.1/v0.2.2 explicitly introduced (`partis-pyproj rebuild`).

#### Step-by-step proof

1. Project declares a target with `entry = 'partis.pyproj.builder:download'` and `filename = 'foo.tar.gz'`. Leave `build_clean` at its default (`False`).
2. First editable install: `pip install -e .`
   - `self.editable=True`, `target.build_clean=False` ⇒ `build_clean=False` (builder.py:203)
   - `build_dir` is empty, `status_file` doesn't exist, no cleaning happens; `.pyproj_status` is written (builder.py:237-238)
   - Download runs: cache miss path executes, `cache_file` is created, then `out_file.symlink_to(cache_file)` succeeds because `out_file` doesn't exist yet.
3. Run `partis-pyproj rebuild .` (or any re-invocation that hits `build_editable`).
   - `build_dir` exists and is non-empty (`build_dirty=True`), `status_file` exists and matches (same commit, same env)
   - Neither branch at builder.py:211 or 218 fires ⇒ `shutil.rmtree(build_dir)` is *not* called.
   - Download runs again: `cache_file.exists()` is true (cache hit), the cache-miss block is skipped.
   - Execution reaches `out_file.symlink_to(cache_file)` at line 147; `out_file` is still the symlink created in step 2.
   - `FileExistsError: [Errno 17] File exists: '…/cache_file' -> '…/build_dir/foo.tar.gz'` is raised, aborting the rebuild.

#### Fix

```python
out_file.unlink(missing_ok=True)
out_file.symlink_to(cache_file)
```

Or, more defensively:

```python
if out_file.is_symlink() or out_file.exists():
    if out_file.is_symlink() and out_file.readlink() == cache_file:
        pass  # already linked correctly
    else:
        out_file.unlink()
        out_file.symlink_to(cache_file)
else:
    out_file.symlink_to(cache_file)
```

---

### 2. Editable install: dependency name lookup not PEP 503 normalized (`KeyError` risk)

- **File:** `src/pyproj/backend.py:329-340`
- **ID:** `merged_bug_010`

Editable install path uses raw `Requirement.name` as both the dict key (`env_reqs[pkg.req.name]`) and the lookup key (`env_reqs[dep.req.name]`), without PEP 503 normalization on either side. If a name in `build-system.requires` differs in case or separator from the installed distribution's METADATA Name (e.g. `My_Pkg` vs `my-pkg`, or `Setuptools` vs `setuptools`), `env_reqs[dep.req.name]` raises a bare `KeyError` that aborts the editable install with no actionable message. The code's own `# TODO` on line 336 acknowledges this. A related but smaller gap exists upstream in `pyproj.py:189-194` where the project's own package is filtered out of `env_pkgs` using `pkg.metadata['Name']` against `{self.pkg_info.name, self.pkg_info.name_normed}` — also not PEP 503 normalized. Fix by canonicalizing both sides via `norm_dist_name` (or `packaging.utils.canonicalize_name`) before keying/looking up.

#### What the bug is

In `backend.py` `build_editable` at lines 329–338, the editable install path constructs a dict keyed by raw `Requirement.name` and then looks it up by another raw `Requirement.name`:

```python
env_reqs = {
  pkg.req.name: pkg.req
  for pkg in [PkgInfoReq(dep) for dep in pyproj.env_pkgs]}

build_deps = []
for dep in pyproj.build_requires:
  # TODO: build_requires names may not be normalized/match those of installed package
  req = env_reqs[dep.req.name]    # KeyError if names disagree on normalization
  build_deps.extend([str(dep.req), str(req)])
```

The `# TODO` on line 336 is the authors' own acknowledgement that this is broken when normalizations differ.

#### Why existing code does not prevent it

`PkgInfoReq` (`pkginfo.py:115`) wraps `packaging.requirements.Requirement`. `Requirement.name` returns the **literal** name as written — it does *not* apply PEP 503 normalization (lowercase, runs of `.`/`-`/`_` collapsed to `-`). So `env_reqs` is keyed by the literal name from `pyproj.env_pkgs` (which itself comes from `pkg.metadata['Name']`), while the lookup uses the literal name from `build-system.requires` as written in `pyproject.toml`. PEP 503 explicitly requires comparison of distribution names to be done on canonical form.

The dict is built with `dict.__getitem__`, not `.get(...)`, so any mismatch is fatal.

#### Step-by-step proof

1. A project declares `build-system.requires = ["Setuptools >= 70", "Cython>=3.0"]` in `pyproject.toml` (note the capitalisation).
2. The current environment has `setuptools` and `cython` installed; `importlib.metadata.Distribution.discover()` yields `pkg.metadata['Name'] == 'setuptools'` and `'Cython'` respectively.
3. `pyproj.env_pkgs` (built in `pyproj.py:190-194`) contains `'setuptools==70.x.x'` and `'Cython==3.0.x'`.
4. In `build_editable`, the comprehension builds `env_reqs = { 'setuptools': ..., 'Cython': ... }` (literal names preserved by `Requirement`).
5. The for-loop iterates over `pyproj.build_requires` whose entries were parsed from the pyproject.toml as written, so `dep.req.name == 'Setuptools'` for the first one.
6. `env_reqs['Setuptools']` raises `KeyError: 'Setuptools'` — `'setuptools'` is in the dict, but `'Setuptools'` is not.
7. The exception is uncaught at this layer, propagates up, and the editable install aborts with an unhelpful traceback. The user sees no hint that the problem is a case mismatch.

#### Related normalization gap (`pyproj.py:189-194`)

```python
project_names = {self.pkg_info.name, self.pkg_info.name_normed}
self.env_pkgs = sorted(set([
  f"{pkg.metadata['Name']}=={pkg.metadata['Version']}"
  for pkg in metadata.Distribution.discover()
  if pkg.metadata['Name'] not in project_names]))
```

The filter compares the raw `pkg.metadata['Name']` against the un-normalized + PEP-503-normalized variants of the declared project name. Mostly works for modern setuptools/build tooling, but not guaranteed by any spec — wheel installers and some legacy distributions can leave METADATA Name in a third equivalent form (e.g. `partis_pyproj` while pyproject has `partis-pyproj`).

#### Fix

```python
# backend.py
from packaging.utils import canonicalize_name  # or use norm_dist_name

env_reqs = {
  canonicalize_name(pkg.req.name): pkg.req
  for pkg in [PkgInfoReq(dep) for dep in pyproj.env_pkgs]}

for dep in pyproj.build_requires:
  req = env_reqs.get(canonicalize_name(dep.req.name))
  if req is None:
    build_deps.append(str(dep.req))  # no pin available, fall back
  else:
    build_deps.extend([str(dep.req), str(req)])
```

```python
# pyproj.py
project_name = self.pkg_info.name_normed
self.env_pkgs = sorted(set([
  f"{pkg.metadata['Name']}=={pkg.metadata['Version']}"
  for pkg in metadata.Distribution.discover()
  if norm_dist_name(pkg.metadata['Name']) != project_name]))
```

The fallback in `build_editable` (use `dep.req` alone when no env pin is found) also removes the `KeyError` for the case where a `build_requires` name is simply not in the current environment at all.

---

### 3. Hardcoded developer-local paths and wrong project name in `docs/conf.py`

- **File:** `docs/conf.py:102-109`
- **ID:** `bug_001`

`docs/conf.py:103-108` hardcodes absolute paths to `/media/box/projects/moebius-n2212/...` (a different developer's local install of another project, nohm/moebius), and sets `html_title = 'MOEBIUS 0.0.1'` / `htmlhelp_basename = 'moebius-0.0.1_doc'` instead of using partis-pyproj. This is a copy-paste error that breaks the documentation build for everyone but the original developer, including the `nox -s doc` session wired up through `docs/__main__.py`. Fix by replacing the absolute paths with project-local `_static`/`_templates` directories (or removing them) and reusing the `project`/`version` variables already derived from `get_meta('partis-pyproj')` earlier in the file.

#### What the bug is

`docs/conf.py` is a Sphinx configuration file. Lines 102-108 contain:

```python
html_static_path = ['/media/box/projects/moebius-n2212/v310/lib/python3.10/site-packages/nohm/document_module/_static']
html_css_files = ['tables.css', 'custom_sig.css']
templates_path = ['/media/box/projects/moebius-n2212/v310/lib/python3.10/site-packages/nohm/document_module/_templates']
html_logo = '/media/box/projects/moebius-n2212/v310/lib/python3.10/site-packages/nohm/document_module/_static/app_icon.svg'
html_title = 'MOEBIUS 0.0.1'
htmlhelp_basename = 'moebius-0.0.1_doc'
```

Two distinct issues:

1. **Hardcoded developer-local absolute paths** referencing a different project (`nohm` / `moebius`) installed under a specific developer's filesystem layout.
2. **Wrong title metadata** — `html_title` and `htmlhelp_basename` are branded for the unrelated `MOEBIUS` project at version `0.0.1`, even though the file already correctly derives the project name and version from `importlib.metadata.metadata('partis-pyproj')` via `get_meta(...)` at line 41.

#### Code path that triggers it

`docs/__main__.py` imports `conf` and invokes `python3 -m sphinx.cmd.build -T -b html <src> <build> -c <conf_dir>` (see `docs/__main__.py:21-33`). This is in turn invoked by the nox `doc` session in `noxfile.py`. So the failure path is:

`nox -s doc` → `python -m docs` → `sphinx.cmd.build` → reads `docs/conf.py` → Sphinx tries to access `html_static_path[0]` and `templates_path[0]` → directory does not exist on disk → error.

#### Fix

Replace lines 103-109 with:

```python
html_static_path = ['_static'] if (Path(__file__).parent/'_static').is_dir() else []
templates_path = ['_templates'] if (Path(__file__).parent/'_templates').is_dir() else []
html_logo = None  # or a project-local SVG/PNG if one is added under docs/_static/
html_title = f'{project} {release}'
htmlhelp_basename = f'{project_normed}-{release}_doc'
html_css_files = []  # drop unless tables.css/custom_sig.css are added under docs/_static/
```

---

### 4. Inconsistent Python version declarations: noxfile/requires-python/CI matrix

- **File:** `pyproject.toml:31-35`
- **ID:** `bug_008`

The project declares `requires-python = ">= 3.8"` and `[tool.noxfile].python` lists `3.8` and `pypy3.9`, but `.github/workflows/tests.yaml` only tests Python 3.9-3.14 + pypy3.10 (no 3.8, no pypy3.9), and the source code unconditionally uses Python 3.9+ features at module import time (PEP 584 dict-merge `|` at `src/pyproj/builder/builder.py:51` and `str.removesuffix()` at `src/pyproj/builder/download.py:191`). The declared 3.8 floor is therefore broken — anyone installing on Python 3.8 will get an `ImportError`/`AttributeError` on first use, and CI cannot catch regressions of the declared minimum. Fix: bump `requires-python` to `>= 3.9` and either drop `3.8`/`pypy3.9` from `[tool.noxfile].python` or add them to the CI matrix so the declared support is actually exercised.

#### What the bug is

`pyproject.toml` makes three Python-version claims that contradict each other and the source code:

1. `[project] requires-python = ">= 3.8"` (line 45) — declared installable floor.
2. `[tool.noxfile] python = ["3.14", ..., "3.9", "3.8", "pypy3.10", "pypy3.9"]` (lines 119-129) — interpreters nox is configured to test against.
3. `.github/workflows/tests.yaml` matrix lists only `"3.9"`-`"3.14"` and `"pypy3.10"` (no `"3.8"`, no `"pypy3.9"`).

So the project advertises 3.8 support, configures nox to run a `test-3.8` session that CI never invokes, and silently drops 3.8/pypy3.9 from the actual test matrix.

#### Why the declared 3.8 floor is actually broken

Independent of the CI gap, the source uses Python 3.9+ syntax at **module top level** (i.e. at import time, not deferred by `from __future__ import annotations`):

- `src/pyproj/builder/builder.py:51` — `_sysconfig_vars = _sysconfig_vars_alt | sysconfig.get_config_vars()`. The `dict | dict` merge operator is [PEP 584](https://peps.python.org/pep-0584/), Python 3.9+. On 3.8 this raises `TypeError: unsupported operand type(s) for |: dict and dict` the moment `partis.pyproj.builder.builder` is imported.
- `src/pyproj/builder/download.py:191` — `_url = _url.removesuffix(/+name)`. `str.removesuffix` was added in Python 3.9. On 3.8 this raises `AttributeError: str object has no attribute removesuffix` whenever the `download` builder runs.

Note: PEP 604 `X | None` union annotations are **not** affected — every module in `src/pyproj/` carries `from __future__ import annotations`, which defers annotation evaluation to strings on 3.8+. The load-bearing evidence is the two 3.9-only API uses above.

#### Fix

Two-part fix:

1. In `pyproject.toml`, change `requires-python = ">= 3.8"` to `">= 3.9"` and drop `"3.8"` and `"pypy3.9"` from `[tool.noxfile].python`.
2. Either keep the noxfile list aligned with the CI matrix (drop 3.8/pypy3.9 from both) or add `"3.8"` / `"pypy3.9"` to `.github/workflows/tests.yaml`. Given the 3.9+ API usage is unconditional and 3.8 is EOL, the simpler fix is to drop 3.8.

---

## Nit severity

### 5. `dist_iter` inner loop shadows outer index, yielding wrong copy_item index

- **File:** `src/pyproj/dist_file/dist_copy.py:82`
- **ID:** `bug_002_1`

The inner loop `for i, (path, info) in enumerate(matches):` at line 82 shadows the outer loop's `i` (the `copy_items` index), so the `i` yielded at line 125 is the per-pattern match index instead of the copy_item index. The consumer in `dist_copy()` passes this to `validating(key=i)`, so validation error paths will report a misleading index when there are multiple copy items or multiple matches under one item. The FileInfo branch (line 60) correctly yields the outer index, making behavior inconsistent.

#### What the bug is

In `src/pyproj/dist_file/dist_copy.py`, `dist_iter` has two nested loops that both bind the name `i`. The outer loop at line 35:

```python
for i, cp in enumerate(copy_items):
```

uses `i` as the index into `copy_items`. The inner loop at line 82:

```python
for i, (path, info) in enumerate(matches):
```

re-binds `i` to the per-include-pattern match index. The yield at line 125 then uses the (shadowed) inner `i`:

```python
yield (i, _src, _dst)
```

while the FileInfo branch at line 60 still uses the outer `i`:

```python
yield (i, src, dst)
```

#### Impact

Error-reporting bug only — actual file selection and copy use `_src` / `_dst`, not `i`. Does not change which files end up in the distribution. But makes debugging copy failures harder when there are multiple copy items, especially in larger projects with several include groups, and the inconsistency between the two yield sites is surprising.

#### Fix

Rename the inner loop variable to avoid shadowing:

```python
for j, (path, info) in enumerate(matches):
    ...
    yield (i, _src, _dst)
```

---

### 6. `build-system.requires` pins very old packaging/tomli inconsistent with project dependencies

- **File:** `pyproject.toml:60-67`
- **ID:** `bug_007`

The `[build-system].requires` pins `packaging == 21.3` and `tomli >= 1.2.3` while `[project].dependencies` declares `packaging >= 24.2` and `tomli >= 2.0.1`. The self-hosting build still works because the backend only uses long-stable APIs (`Requirement`/`SpecifierSet`/`Marker`/`sys_tags`) and `VERSION_PATTERN` is hard-coded in `pep.py`, but the strict `==` pin is a maintenance trap: any future use of a packaging API added after 21.3 will silently work in editable/installed scenarios while failing in build isolation. Recommend loosening the build constraint to mirror the runtime range (e.g. `packaging >= 24.2`, `tomli >= 2.0.1`).

#### Why this is currently fine

`pep.py` only touches `packaging.requirements.Requirement`, `packaging.specifiers.SpecifierSet`, `packaging.markers.Marker`, and `packaging.tags.sys_tags`, all of which have been stable since well before 21.3. `VERSION_PATTERN` is intentionally hard-coded as a verbatim copy in `pep.py` (lines 484-507). `partis-pyproj` is purelib-only, so `platlib_compat_tags()`/`sys_tags()` is never invoked during its self-hosting build.

#### Why it's still worth flagging

1. *Asymmetric API surface*: if a contributor adds a call to a `packaging` API introduced after 21.3, tests run against installed packages will pass, the editable workflow will pass, but a fresh `pip wheel .` / `python -m build` in isolation will get `AttributeError` or `ImportError` from the build backend itself.
2. *The strict `==` pin actively rejects newer environments*: a user who already has `packaging==25.0` installed and wants to build with `--no-build-isolation` will get a constraint failure.

#### Fix

```toml
[build-system]
requires = [
  "packaging >= 24.2",
  "tomli >= 2.0.1" ]
```

No need to add `requests` to `build-system.requires` — `builder/download.py` imports `requests` lazily inside the `download()` function.

---

### 7. `dist_binary_editable.write`/`copyfile`: LSP signature mismatch and `exist_ok` not propagated to `record()`

- **File:** `src/pyproj/dist_file/dist_binary.py:444-467`
- **ID:** `merged_bug_003`

`dist_binary_editable.write` drops the `exist_ok` parameter from the `dist_base.write` signature, violating LSP. The same override and `copyfile` (line 407) also fail to forward `exist_ok` to `self.record()`, so the `exist_ok=True` intent is not honored end-to-end. No current caller passes `exist_ok=True` to an editable instance so the issue is latent; fix is to add the parameter and forward it to `_dst.write_bytes`/`self.record`.

#### The defect

`dist_base.write` (`dist_base.py:128-150`) is declared as `write(self, dst, data, mode=None, exist_ok=False, record=True)`. The override `dist_binary_editable.write` (`dist_binary.py:444-467`) is declared as `write(self, dst, data, mode=None, record=True)` — `exist_ok` is missing entirely. Any caller that uses the base contract `write(..., exist_ok=True)` against an editable instance will get `TypeError: write() got an unexpected keyword argument 'exist_ok'`.

Additionally, the override calls `_dst.write_bytes(data)` unconditionally with no `exists()` check, and then calls `self.record(dst=dst, data=data)` with no `exist_ok` forwarded. `dist_base.record` defaults `exist_ok=False` and raises `ValidationError` on a non-equivalent overwrite. The companion `dist_binary_editable.copyfile` (line 407) does accept `exist_ok` but only uses it for the early `self.exists()` check at line 422 — at lines 437-439 it calls `self.record(dst=dst, data=str(_dst).encode('utf-8'))` without forwarding `exist_ok`. By contrast `dist_zip.write` correctly passes `exist_ok=exist_ok` to `self.record`.

#### Why this is currently latent

- `dist_base.copytree` does eventually call `copyfile` with `exist_ok=...`, but `dist_binary_editable.copyfile` is fully overridden and uses `_dst.symlink_to(src)` directly — it never calls `self.write`.
- `write_link` is inherited but only calls `self.record(..., exist_ok=...)`, and `record` does accept `exist_ok`.
- The override `dist_binary_editable.finalize` builds a *separate* `dist_binary_wheel` instance and writes the `.pth` file through that wheel, not through `self.write`.
- No current code path passes `exist_ok=True` to an editable instance.

#### Fix

```python
def write(self, dst, data, mode=None, exist_ok=False, record=True):
    self.assert_open()
    dst = norm_path(os.fspath(dst))
    _dst = self.whl_root/Path(dst)
    if _dst.exists() and not exist_ok:
        raise PathError(f"Build file already has entry: {dst}")
    if not _dst.parent.exists():
        _dst.parent.mkdir(parents=True)
    data = norm_data(data)
    _dst.write_bytes(data)
    if record:
        self.record(dst=dst, data=data, exist_ok=exist_ok)
```

And in `copyfile`, change line 437-439 to `self.record(dst=dst, data=str(_dst).encode('utf-8'), exist_ok=exist_ok)`.

---

### 8. `build_wheel` finalize: non-recursive metadata_directory iteration breaks PEP 517 contract

- **File:** `src/pyproj/dist_file/dist_binary.py:227-244`
- **ID:** `bug_021`

In `dist_binary_wheel.finalize` (`dist_binary.py:235`), the loop that integrates files from a previously-built `metadata_directory` uses `Path(metadata_directory).iterdir()`, which is non-recursive. If the dist-info contains any subdirectory (e.g. a PEP 639 `licenses/` subdir, or any other tree emitted by a different frontend's `prepare_metadata_for_build_wheel`), the directory entry is passed straight to `self.copyfile(file, _file)` which calls `open(src, 'rb')` and raises `IsADirectoryError`, aborting the wheel build. Even if that were guarded, files beneath the subdirectory would be silently dropped, violating PEP 517's requirement that the final `.dist-info` MUST be identical to the one produced by `prepare_metadata_for_build_wheel`.

#### What the bug is

```python
for file in Path(metadata_directory).iterdir():
    if file.name == 'RECORD':
        continue
    _file = dist_info/file.relative_to(metadata_directory).as_posix()
    if self.exists(_file):
        continue
    self.copyfile(file, _file)
```

`Path.iterdir()` only yields top-level entries — it does not recurse. And nothing checks whether the yielded entry is a directory before handing it to `self.copyfile`.

`self.copyfile` (inherited from `dist_base.copyfile` at `dist_base.py:206`) does:

```python
if not src.exists():
    raise ValueError(...)
...
with open(src, 'rb') as fp:
    self.write(dst=dst, data=fp, ...)
```

`open(<directory>, 'rb')` raises `IsADirectoryError` on POSIX.

#### Impact

- PEP 639 introduces a `licenses/` subdirectory under `.dist-info` for the license-files manifest. A frontend that emits PEP 639 license bundles in `prepare_metadata_for_build_wheel` will cause `build_wheel` to crash on the `licenses/` entry.
- Any third-party frontend that passes a path with subdirectories to `build_wheel` will hit the same crash.
- Even if the crash were avoided, the recursive contents would be silently dropped, producing a wheel whose `.dist-info` is *not* identical to the prepared one.

#### Fix

```python
md_root = Path(metadata_directory)
for file in md_root.rglob('*'):
    if not file.is_file():
        continue
    rel = file.relative_to(md_root).as_posix()
    if rel == 'RECORD':
        continue
    _file = dist_info / rel
    if self.exists(_file):
        continue
    self.copyfile(file, _file)
```

Symlinks within the dist-info should ideally be handled via `dist_base.write_link` to preserve PEP 491 semantics.

---

### 9. `pkgaux/utils.py`: `session.run` called with list, swallowed by bare except

- **File:** `pkgaux/utils.py:110-130`
- **ID:** `bug_013`

`clear_pip_cache` in `pkgaux/utils.py` is a silent no-op on multiple levels: (1) it's called from `noxfile.py:86` with the string `'partis-pyproj'`, so `for pkg in pkgs:` iterates over individual characters; (2) `session.run([...])` passes a list as the first positional arg, but nox's `Session.run` is declared `def run(self, *args: str, ...)` and expects each argv element as a separate positional — see the correct usage in the same file at `pkgaux/utils.py:127` (`session.run(*[str(v) for v in args])`); (3) the bare `except: pass` swallows the resulting `TypeError` silently. Net effect: the pip cache is never cleared, defeating the comment intent at line 98 ("remove from the pip cache to prevent using a previously installed distro").

#### Why existing code doesn't prevent it

There is no defensive check that `pkgs` is a list rather than a string. The bare `except:` is the opposite of defensive — it hides the very `TypeError` that would otherwise reveal the call-shape mismatch. The author clearly knows the correct `session.run` convention (used right below at line 127), but those callsites use the wrong shape and the exception handler masks the mistake.

#### Impact

Limited to development tooling. The package's runtime behavior, the PEP-517 backend itself, and the published wheel are unaffected. `nox -s prepare` will continue to succeed because the errors are swallowed. The practical consequence is that stale cached partis-pyproj wheels may be used during repeated local `nox -s prepare` runs.

#### Fix

Two changes:

1. In `noxfile.py:86`, pass a list: `clear_pip_cache([pkg])`.
2. In `pkgaux/utils.py:100-122`, unpack the args, remove the literal quotes around the pattern (pip is *not* invoked through a shell), and narrow the exception handler:

```python
@session_command
def clear_pip_cache(session, pkgs):
  for pkg in pkgs:
    try:
      session.run(
        'python', '-m', 'pip', 'cache', 'remove',
        f"{pkg.replace('-','_')}*")
    except Exception:
      pass

  try:
    session.run('python', '-m', 'pip', 'uninstall', '-y', *pkgs)
  except Exception:
    pass
```
