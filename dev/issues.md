# partis-pyproj — issues found while debugging a nohm-core editable install

Context: discovered 2026-07-23 while installing `nohm-core` (1.4.1.dev5) editable into a
uv venv, build-backend `partis.pyproj.backend`. Source read at commit in
`/work/media/cdodd/box/projects/common/partis-pyproj` (version 0.2.3); the failure
reproduced against the installed 0.2.2, same code paths. File paths below are
`src/pyproj/backend.py` (installed as `partis/pyproj/backend.py`).

Both are S2. Neither blocks work today (worked around), but both cost a debugging session
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

---

## Issue 2 — editable build is non-atomic: a failed rebuild destroys the previously-working install

**Where:** `backend.py:315-317` (`build_editable`).

```python
if editable_root.exists():
    # TODO: add status file to avoid accidentally deleting the wrong directory
    shutil.rmtree(editable_root)
```

**Problem.** The entire editable root (including the working `wheel/` tree that the
`.pth` points at) is deleted *before* the new build runs. If the build then fails (e.g.
Issue 1), the package is left uninstalled/unimportable — a previously-working environment
is broken by an attempt to rebuild it. Observed directly: a failing `pip install -e` left
`import nohm.core` raising `ModuleNotFoundError` until the tree was hand-reconstructed.

**Proposed fix.** Build into a staging directory and atomically `os.replace()`/rename into
place only after the build succeeds; on failure, leave the existing editable untouched. A
failed rebuild then becomes a no-op rather than a breakage. (The line-316 TODO already
gestures at more careful handling of this directory.)

**Test idea.** Given a working editable install, run a build that fails partway → assert the
prior `wheel/` tree and importability are unchanged.

---

## Not a partis-pyproj bug (recorded for completeness)

- The `nohm` namespace: nohm-core's `pyproject.toml` deliberately excludes `./__init__.py`
  from the dist ("so 'nohm' becomes implicit namespace"), and partis-pyproj honors it
  correctly. A shadowing `nohm/__init__.py` only appeared when the tree was hand-copied from
  `src/`; the real build does the right thing. No change needed.

## Ideas

- Have editable virtual wheel be located within repo somewhere. (a location option?)