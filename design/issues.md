# partis-pyproj — issues found while debugging a nohm-core editable install

Context: discovered 2026-07-23 while installing `nohm-core` (1.4.1.dev5) editable into a
uv venv, build-backend `partis.pyproj.backend`. Source read at commit in
`/work/media/cdodd/box/projects/common/partis-pyproj` (version 0.2.3); the failure
reproduced against the installed 0.2.2, same code paths. File paths below are
`src/pyproj/backend.py` (installed as `partis/pyproj/backend.py`).

Neither blocks work today (worked around), but both cost a debugging session
and one broke a working environment.

---

## Issue 1 — `build_requirements` self-conflicts when the installed build-dep version violates a tightened build spec

**Where:** `backend.py:335-349` (`build_editable`).

**What it does now.** For each `[build-system].requires` entry it appends *both* the spec
and a hard pin to the currently-installed version:

```python
for dep in pyproj.build_requires:
    build_deps.append(str(dep.req))                 # e.g. "Cython~=3.1.3"
    req = env_reqs.get(norm_dist_name(dep.req.name))
    if req is not None:
        build_deps.append(str(req))                 # e.g. "Cython==<installed>"
```

The intent (comment at 327-328) is to reproduce the current build environment on
incremental builds by pinning to installed versions.

**Failure.** When the installed version does not satisfy the spec — e.g. `[build-system]`
was tightened to `Cython ~= 3.1.3` but the venv still had `Cython 3.0.12` — the generated
`build_requirements.txt` contains both `Cython~=3.1.3` and `Cython==3.0.12`, which is
unsatisfiable. `uv pip install -r build_requirements.txt` then fails with a resolver error
("because you require cython>=3.1.3,<3.2 and cython==3.0.12 …") that does not name the real
cause (installed version is stale relative to the tightened spec).

**Proposed fix (backend.py:344-347).** Before appending the `==installed` pin, check it
satisfies `dep.req` (the spec). If it does, pin as today. If it does not, either:
- (a) drop the pin and let the resolver pick a spec-satisfying version (auto-upgrades the
  build dep), or
- (b) raise a clear diagnostic: "installed Cython 3.0.12 does not satisfy build requirement
  Cython~=3.1.3; upgrade with `uv pip install -U cython`."

(a) is more automatic; (b) is safer/explicit. Could be config-gated. Note the adjacent TODO
at line 329 ("use constraints file instead") would *not* fix this on its own — a `==3.0.12`
constraint still conflicts with a `~=3.1.3` requirement; the satisfiability check is the fix.

**Test idea.** Editable build where an installed build dep is pinned below a tightened
`[build-system]` spec → assert either a clean spec-satisfying resolution (option a) or a
diagnostic naming the package + both versions (option b), not a raw resolver conflict.

**Status.** Option (a) implemented, with a warning naming the package, installed version,
and spec; see `releases.md` v0.2.4. Test: `tests/test_14_editable.py`
`test_build_requirements_pin`.

---

## Issue 2 — editable root is global, keyed only by package name/version/python

**Where:** `pyproj.py:208-210`.

```python
pkg_name = norm_dist_filename(self.pkg_info.name_normed)
pyversion = '.'.join(str(n) for n in sys.version_info[:3])
self.editable_root = cache_dir()/'editable'/f'{pkg_name}_{self.pkg_info.version}_py{pyversion}'
```

`cache_dir()` is `~/.cache/partis-pyproj` (or a username-suffixed temp dir; `cache.py:8-23`).

**Problem.** The symlink-farm path is a function of (package name, version, python version)
only — not of the source tree. Two *distinct source trees* at the same version therefore
share one farm: two worktrees or checkouts of the same package, each installed editable into
its own venv. The second install overwrites the first's `wheel/` tree while the first venv's
`.pth` still points at it, so one environment silently starts importing the other tree's
build. The overwrite is a `rmtree` (`backend.py:315-317`) of a tree another venv depends on.

**Scope.** In farm-per-tree terms, three configurations:

| venvs | farms | trees | status |
|---|---|---|---|
| 2 | 2 | 2 | works today; unchanged |
| 2 | 1 | 2 | the clobbering bug — what this issue fixes |
| 2 | 1 | 1 | not handled, before or after |

Two venvs sharing one tree share one farm. That is not supported and this issue does not
change it; see the structural limit below for why no backend-side key would.

**Proposed fix.** Move the editable root in-tree, consistent with build targets
(`build_dir` defaults to `build/tmp`, `prefix` to `build`).

Decided form: `tool.pyproj.editable` is a **table**, initially carrying a single key
`build_dir`, default `build/editable`, resolved relative to the project root. A table (not a
bare path) so further keys can be added without a schema break. Sketch, added to the
`pyproj` schema's `default` (`pptoml.py:439-446`):

```python
class pyproj_editable(valid_dict):
  allow_keys = list()
  default = {
    # NOTE: paths should start as POSIX, but transformed to current OS
    'build_dir': valid('build/editable', PurePosixPath, Path) }
```

The existing per-install subdirectory is **retained beneath** `build_dir`:

```python
self.editable_root = <build_dir>/f'{pkg_name}_{self.pkg_info.version}_py{pyversion}'
```

so the leaf name is unchanged and only the parent moves from `cache_dir()/'editable'` to an
in-tree path. This removes the cross-tree collision by construction (distinct trees →
distinct parents) and keeps version/python discrimination within one tree.

`build_dir` is constrained to lie within the project root, as elsewhere. The existing
enforcement for target paths is `builder.py:158-181` — non-absolute paths joined to
`self.root`, `resolve()`d, then rejected with `FileOutsideRootError` if not a subdir of the
root (or tmpdir), and rejected if equal to the root itself. Reuse that check.

**Structural limit — the target venv is not observable at build time.** Keying the path by
the installing venv is not available to a PEP 517 backend. Under build isolation the
frontend runs the backend in an ephemeral build environment, so `sys.prefix` /
`sys.executable` name that environment (or the base interpreter it was created from), never
the venv the wheel is about to be installed into; the frontend passes no target-env
identity in `config_settings`. Worse than merely absent: with `--no-build-isolation` the
observable venv *is* the target, so a venv-derived key would make the editable path depend
on how the install was invoked rather than on what was installed, and an isolated and a
non-isolated install of the same tree would disagree about where the farm lives. Note
`backend.py:351-355` already creates its own `build_venv` inside the editable root from
`sys.executable` for later rebuilds — that is the build interpreter, not the target venv.

This is why the third row of the scope table stays unhandled: one tree in two venvs is one
farm, and no backend-side key separates them.

**`./build` is not excluded from the distribution, by design.** The convention is that
`./build` holds all build products — wheels, docs, anything generated — functioning as a
build-specific tmp directory. Keeping the editable farm at `build/editable` follows that
convention. Excluding it from the sdist/wheel is the project's responsibility via its own
dist copy patterns, not something the backend does implicitly; the default gains no special
ignore.

**The `--staging` CLI option is removed.** `cli/build_pyproj.py:54-58` currently lets the
caller override the editable root per-invocation. Once `build_dir` is declared in
`pyproject.toml`, that override is a second, conflicting source of truth for the same path —
and a rebuild pointed at a different root than the install used produces a farm no `.pth`
references. The location comes from the project config only.

Follow-on, read as implied rather than stated: `_rebuild_pyproj`'s `editable_root`
parameter (`cli/build_pyproj.py:74-85`, including the `if editable_root is None` fallback)
also goes, leaving the function to always use `pyproj.editable_root`. Flagged because
`tests/test_17_cli_rebuild.py` passes that parameter directly in three tests; they would
move to setting `build_dir` in the fixture's `pyproject.toml` instead. If the parameter
should survive as a library-level seam with only the argparse flag removed, say so.

**Leaf name retained.** `{pkg}_{version}_py{X.Y.Z}` stays as-is beneath `build_dir`. Version
and python still discriminate within a single tree, and keeping the name means the change is
strictly a reparenting.

**Work items.**
- `pptoml.py` — add `pyproj_editable` with `build_dir`; register under the `pyproj` schema
  `default` (`pptoml.py:439-446`).
- `pyproj.py:208-210` — build `editable_root` from the configured `build_dir` instead of
  `cache_dir()/'editable'`; apply the in-root check per `builder.py:158-181`.
- `backend.py:311-330` — consumes `pyproj.editable_root`; no change needed.
- `cli/build_pyproj.py` — drop `--staging` and the `editable_root` parameter.
- `cache.py` — unchanged. `cache_dir()` stays: the download builder uses it
  (`builder/download.py:196` and `builder/builder.py:99`, both `cache_dir()/'download'`), and
  a global cache is right there — downloads are content-fetched by URL and genuinely shared
  across projects. What this issue removes is the use of `cache_dir()` for *install state*,
  which is per-tree and per-venv rather than shared. Two dead imports fall out:
  `backend.py:39` and `cli/build_pyproj.py:12` both import `cache_dir` without using it
  already.

**Tests to add.**
- Two checkouts of the same package at the same version, installed editable into two venvs
  on one interpreter → each `.pth` resolves to a distinct tree under its own source root, and
  building one does not modify the other. (Row 2 of the scope table — the regression test for
  this issue.)
- Default location → farm lands in `build/editable/{pkg}_{version}_py{X.Y.Z}`.
- `tool.pyproj.editable.build_dir` set → farm lands there.
- `build_dir` escaping the root (`../elsewhere`, absolute outside root, or the root itself)
  → `FileOutsideRootError` / `ValidPathError`, matching target-path behavior.

**Existing tests to update.**
- `tests/test_14_editable.py:44-52, 90-107` — monkeypatches `cache.CACHE_DIR` and reconstructs
  the expected path under it. The monkeypatch becomes unnecessary; assertions move to the
  in-tree path.
- `tests/test_14_editable.py:126` — invokes the CLI with `--staging`; breaks on removal.
- `tests/test_17_cli_rebuild.py:71-125` — four tests built around the `editable_root`
  parameter, including `test_rebuild_default_editable_root` which exists to cover the
  `editable_root=None` fallback being deleted. Rework against configured `build_dir`.

**Status.** Implemented as decided above, including removal of `--staging` and of
`_rebuild_pyproj`'s `editable_root` parameter; see `releases.md` v0.2.4.

---

## Issue 3 — editable wheel metadata does not reflect prep hooks

**Where:** `backend.py` (`build_editable`), `pyproj.py` (`dist_binary_prep`).

**What it does now.** `build_editable` runs `partis-pyproj prep` inside the editable build
venv, so `tool.pyproj.dist.prep` and `tool.pyproj.dist.binary.prep` hooks execute in that
subprocess. The wheel is written by the parent process from the parent's `PyProjBase`,
which does not run those hooks.

**Effect.** Metadata a hook assigns to the parent object is dropped from the editable
wheel: `binary.build_number`, `binary.build_suffix`, and `binary.compat_tags` are read by
`build_editable` from the un-prepped parent object. Observed with `tests/pkg_base`, whose
`dist_binary_prep` sets `build_number = 123` and `build_suffix = 'test'`: the editable
wheel is `test_pkg_base-0.0.1-py3-none-any.whl`, where a non-editable wheel from the same
hooks is `test_pkg_base-0.0.1-123_test-py3-none-any.whl`.

**History.** Before v0.2.4, packages with no enabled build targets ran
`dist_prep`/`dist_binary_prep` in the parent process and did not create a build venv, so
their metadata was carried into the wheel; packages with enabled targets already had this
defect. Removing that branch — so prep hooks always run with the pinned build
dependencies — made the behavior uniform.

**Options, not adjudicated.**
- Round-trip: the in-venv prep writes the prepped metadata into the editable root, and the
  parent reads it before writing the wheel. Keeps hooks in the build venv only; adds an
  on-disk interface between the two processes.
- Also run the `dist.binary.prep` entry point in the parent, without `Builder`, so targets
  are not built twice. Restores the metadata; the hook then runs twice per build, once in
  an environment that may lack the build dependencies the venv exists to provide.

**Test idea.** Editable build of a package whose `dist.binary.prep` sets `build_number`
and `build_suffix` → assert the wheel filename carries them.

---

## Not a partis-pyproj bug (recorded for completeness)

- The `nohm` namespace: nohm-core's `pyproject.toml` deliberately excludes `./__init__.py`
  from the dist ("so 'nohm' becomes implicit namespace"), and partis-pyproj honors it
  correctly. A shadowing `nohm/__init__.py` only appeared when the tree was hand-copied from
  `src/`; the real build does the right thing. No change needed.

## Ideas

- (Moved to Issue 2: locate the editable virtual wheel within the repo, via a location
  option.)