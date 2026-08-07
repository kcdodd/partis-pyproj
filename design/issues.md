# partis-pyproj — issues

## Issue 3 - Python 3.9 (ubuntu, macos, windows): nox cannot start

nox dies on import, before any session runs. The workflow installs nox with the matrix interpreter (tests.yaml:60-67 → pip install -r pkgaux/base_requirements.txt, then nox -s prepare test-3.9), so nox and its dependency argcomplete
are installed under 3.9:

nox/_options.py:25       import argcomplete
argcomplete/completers.py:35   choices: Final[Mapping[str, str | bytes]]
TypeError: unsupported operand type(s) for |: 'type' and 'type'
(21_os ubuntu, python 3.9.txt:263-277; identical at 17_os macos…:290 and 18_os windows…:291.)

argcomplete 3.7.1 (resolved transitively — base_requirements.txt pins only nox ~= 2024.10.9) evaluates a PEP 604 union in a class body with no from __future__ import annotations, which is a runtime error on 3.9. Upstream bug, but it
lands here because the runner runs nox under the version being tested.

Two fixes, both in this repo:
- Constrain it: argcomplete < <last version supporting 3.9> ; python_version < "3.10" in pkgaux/base_requirements.txt — you'd need to confirm which release that is.
- Or decouple the nox host from the target: install nox under a fixed modern interpreter and let nox create the 3.9 venv itself. This removes the whole class of "tool doesn't support the oldest matrix entry" failure, which will recur.

### Resolution

The version question in the first option resolves to argcomplete 3.7.0: 3.7.1 is a
mis-declared release (`requires_python >= 3.8` while `completers.py:35` evaluates a PEP 604
union at class-body scope), and 3.7.2 corrected the metadata to `>= 3.10`. A `!= 3.7.1`
bound would therefore have been sufficient. Receipt: PyPI JSON `requires_python` per
release, plus the 3.7.0/3.7.1 wheel sources.

The second option was taken instead (tests.yaml). Two `setup-python` steps run in order —
target, then `NOX_HOST_PYTHON` (3.13) — so the host wins on PATH and becomes `python`; the
target only needs to be discoverable. `tool.noxfile.default_venv_backend = "uv"`, and uv
falls back to a managed-interpreter download when a requested version is not on PATH, so
target availability does not depend on runner toolcache layout. The `report` job's pinned
3.10 was moved onto the same variable.

`base_requirements.txt` is unchanged, so running `nox` directly under 3.9 outside CI still
hits the argcomplete break. Unverified: uv's discovery/download of the Windows toolcache
pypy3.10, and whether uv 0.8.12's download table carries a final CPython 3.14 — both jobs
currently pass, and both would regress to a nox-startup error, not a silent skip.

Receipt, local, host 3.14 → target 3.9 (the previously unreachable configuration):
`nox -s prepare test-3.9` → `prepare: success`, uv downloaded cpython-3.9.21,
`236 passed, 3 warnings in 119.81s`, exit 0. This exercises the decoupling but not the
Windows/macOS runners.

## Issue 4 - Windows CPython 3.10–3.14: test_08_pyproj.py::test_meson_1

One test fails, identically on all five CPython Windows jobs. Chain, from 8_os windows, python 3.10.txt:380-595:

1. run_pyproj('pkg_meson_1') → try_dist → pip install …/test_pkg_meson_1-0.0.1.tar.gz (build isolation).
2. The backend runs meson setup from the pip build env: pip-build-env-x928stxh\overlay\Scripts\meson.EXE.
3. tests/pkg_meson_1/meson.build:11 — py_mod.find_installation('python3'). Asking by name makes meson search PATH; Windows venvs and pip build-env overlays contain python.exe, not python3.exe, so it resolves to the setup-python tool
cache: C:\hostedtoolcache\windows\Python\3.10.11\x64\python3.EXE.
4. meson's sanity probe of that interpreter fails on stdlib imports — mesonbuild/scripts/python_info.py:15 import json, os, sysconfig → ModuleNotFoundError: No module named 'json', and an earlier probe No module named 'traceback'.
5. → MesonException: <PythonExternalProgram 'python3' -> [...python3.EXE]> is not a valid python or it is missing distutils → BuildCommandError → failed-wheel-build-for-install → CalledProcessError in the test.

Checked, not inferred: the same tool-cache interpreter's stdlib works elsewhere in the same job — the pytest traceback itself comes from C:\hostedtoolcache\windows\Python\3.10.11\x64\lib\subprocess.py:369. So the interpreter is not
broken; it fails only under the environment meson gives the probe.

Why that probe loses the stdlib is not determinable from these logs. partis-pyproj's own error formatter prints only the last 20 lines per window (⋮ markers throughout), and the full evidence is in two files CI discards:
…\build\meson\meson-logs\meson-log.txt and …\build\logs\target_00.meson_EXE.00.log, both under the pip temp build dir. If you want the root cause rather than the fix, upload those (or raise the tail limit) on a Windows re-run.

The fix does not depend on that answer: find_installation() with no argument makes meson use the interpreter it is running under — the build environment's python — instead of searching PATH for a name that does not exist in Windows
environments. All three meson fixtures use the 'python3' form (pkg_meson_1, pkg_meson_2, pkg_meson_bad_1, each at meson.build:11).

Supporting evidence for the name-resolution reading: Windows pypy3.10 passed — 228 passed, 0 skipped (14_os windows, python pypy3.10.txt:366). So it is not "all Windows", it is Windows CPython. The pass/fail split tracks what python3
resolves to in each environment; that the pypy environment exposes a working python3 is my inference, not something these logs show.

Masked failures

Windows jobs collected 228 items and then stopping after 1 failures (--maxfail=1 in pyproject.toml:137): 135 passed, 1 failed, 92 tests never ran. Expect test_meson_2 and test_meson_bad_1 to fail the same way once test_meson_1 is
fixed — they share the find_installation('python3') line. test_cmake_1 is unexercised on Windows and its status is unknown.

### Resolution

`find_installation('python3')` → `find_installation()` in all three fixtures
(pkg_meson_1, pkg_meson_2, pkg_meson_bad_1, each meson.build:11). On POSIX this is expected
to be a no-op: a venv's `python3` already *is* `sys.executable`, so only Windows behaviour
changes. Unverified: the Windows outcome itself — no Windows runner was available, and the
root cause of the stdlib-less probe environment remains undetermined.

Receipt, local Linux/3.9: test_08_pyproj.py 14 passed, including test_meson_1,
test_meson_2, test_meson_bad_1 and test_cmake_1 — i.e. no POSIX regression from the change.

Not changed: `--maxfail=1` (pyproject.toml:137). It still truncates a failing CI job at the
first failure, so a Windows re-run that fails elsewhere will again leave ~90 tests
unreported. test_cmake_1 passes locally on Linux; its Windows status is still unknown, and
its interpreter lookup is a different mechanism (CMake `find_package(Python3)` with
`Python3_FIND_STRATEGY LOCATION`), not the meson PATH-name defect. Note that the Issue 3
fix reassigns the `Python3_ROOT_DIR` / `pythonLocation` variables setup-python exports, from
the matrix version to the nox host; observed locally, CMake resolved the nox session venv's
`python3.9` rather than any hint directory, which is `Python3_FIND_VIRTUALENV=FIRST`
behaviour and should carry to Windows, but this is inference, not a Windows measurement.

