# Releases

## v0.2.1 - 2025-09-07

- Support editable installs according to [PEP 660](https://peps.python.org/pep-0660/).
- Add support for incremental rebuilds in editable installs (with caveats).
- Add CLI command `partis-pyproj {init,build} ...`.
  - `init`: Creates a minimal pyproject.toml from a project folder.
  - `build --incremental`: Manually trigger an incremental rebuild.
- Stricter type validation.
- Ignore overwrite errors for exact-duplicate distribution files.

## v0.2.0 - 2025-04-25

- Relax rule for entrypoint names to allow any characters except `=` or `[`.
- Add a `strip` parameter to `copy`, dropping leading path segments
- Update rules for `extra` names according to [PEP 685](https://peps.python.org/pep-0685/).
- Add support for `dependency-groups` according to [PEP 735](https://peps.python.org/pep-0735/).
- Allow logging level configuration via `PYPROJ_LOG_LEVEL` (if
  frontend does not already configure logging).
- `glob` now only matches individual filenames, not directories (fixes recursive copying of directories by glob + copytree).
- Verify download status codes and handle empty download files.

## v0.1.9 - 2025-03-31

- Correct value comparison logic between validation of ``tool.pyproj.config`` and ``config_settings``.

## v0.1.8 - 2025-03-13

- Correct CMake argument order
- Collapse validation error stacks for cleaner messages.

## v0.1.7 - 2025-02-27

- Add builder `partis.pyproj.builder:download`, support caching and archive extraction.

## v0.1.6 - 2025-01-03

- Restore backward-compatible `meson` attribute (still deprecated).

## v0.1.5 - 2024-12-13

- Add target template variable substitutions.
- Support pypy interpreter.
- Fix Windows path resolution and CMake issues for mingw-64.

## v0.1.4 - 2024-10-10

- Add `partis.pyproj.builder:process`.
- Adjust include/ignore rules.
- Fix wheel record CSV formatting and version usage in tests.

## v0.1.0 - 2022-11-14

- Generalize build steps in `tool.pyproj.targets`.
- Add builder `partis.pyproj.builder:meson`, replacement for now deprecated `tool.pyproj.meson`.
- Add builder `partis.pyproj.builder:cmake`.
- Replace `os.path` with `pathlib` throughout codebase.
- Fix entry-point module loading and attribute names.
- Normalize paths and refactor filename pattern matching.

## v0.0.1 - 2022-07-18
- Initial packaging for PyPI distribution with separate documentation builds.
