# Releases

## v0.3.2 - 2026-09-01

- Fix unicode handling in PKG-INFO and METADATA
- No longer strip unassigned (Cn) characters from meta-data. Which code points
  are unassigned depends on the Unicode version of the interpreter, so
  stripping them made the emitted meta-data differ between interpreters and
  silently deleted every character assigned by a later Unicode release.
  Control (Cc), surrogate (Cs), private use (Co), line/paragraph separator
  (Zl, Zp) and the permanently reserved noncharacters are still stripped;
  those sets are immutable under the Unicode stability policy.
- Strip the explicit directional formatting characters (U+202A-U+202E,
  U+2066-U+2069) and the byte order mark (U+FEFF) from meta-data. Keeping the
  format characters (Cf) is what lets emoji and Indic text through, but the
  directional embeddings, overrides and isolates re-order the display of the
  text that follows them, so a rendered value could be made to disagree with
  the source it was written from. The implicit directional marks (U+200E,
  U+200F, U+061C) and the joiners (U+200C, U+200D) are unaffected.
- A 'readme' or 'license' file that is not valid UTF-8 is now an error,
  reporting the line and column of the first undecodable byte. Previously it
  was decoded with replacement characters, so the meta-data silently shipped
  content the author never wrote, with no indication of where.


## v0.3.1 - 2026-08-12

- Fix leaking of env from parent interpreter into editable build_venv

## v0.3.0 - 2026-08-10

- Move the editable staging directory into the project tree, at
  `tool.pyproj.editable.build_dir` (default `build/editable`), instead of
  `$HOME/.cache/partis-pyproj/editable`. Two checkouts of the same package and
  version no longer share (and overwrite) one staging directory.
- Remove `partis-pyproj rebuild --staging`; the location comes from
  `pyproject.toml` only.
- Only pin an editable build dependency to the installed version when that version
  satisfies the declared requirement. Previously both were written to
  `build_requirements.txt`, which is unsatisfiable when the installed version is
  stale relative to a tightened `[build-system].requires`. A warning now names the
  package, installed version, and requirement, and the resolver picks a satisfying
  version.
- Always create the editable build environment, including when no build targets are
  enabled, since `prep` hooks may also need the build dependencies. Note that
  metadata assigned by a `prep` hook (`build_number`, `build_suffix`,
  `compat_tags`) no longer reaches the editable wheel for such packages; see
  Issue 3 in `design/issues.md`.

## v0.2.2 - 2026-05-19

- Add support for Python 3.14
- Fix `pyproj.config` keys replacing `_` with `-`.
- Loosen conditions when clean build is triggered, `target.build_clean = False` is
  now the default.
- Add Python version to editable virtual wheel folder name
- Split CLI command `partis-pyproj build` into `partis-pyproj prep` which runs
  the build targets, and `partis-pyproj rebuild` which runs the "prep" command
  in the build virtual environment.

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
