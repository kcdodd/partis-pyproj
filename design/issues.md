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

