# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`partis-pyproj` is a minimal PEP-517 build back-end. It is self-hosting: the repo uses its own backend (`build-backend = "pyproj.backend"`, `backend-path = ['src']`) to build itself. Source lives in `src/pyproj/` but is installed under the `partis` namespace package as `partis.pyproj`.

## Commands

### Install development dependencies
```sh
pip install -r pkgaux/base_requirements.txt
```

### Build sdist and wheel (required before running tests via nox)
```sh
nox -s prepare
```

### Run tests (all Python versions defined in pyproject.toml)
```sh
nox -s test
```

### Run tests for a specific Python version
```sh
nox -s test-3.11
```

### Run tests directly with pytest (faster, no nox isolation, uses installed package)
```sh
pytest tests/
```

### Run a single test file
```sh
pytest tests/test_05_dist.py
```

### Generate coverage report
```sh
nox -s report
```

### Lint and type checking
```sh
ruff check src/
mypy src/
```

## Architecture

### Source layout
- `src/pyproj/` — source, installed as `partis/pyproj` (namespace package)
- `tests/` — pytest test suite plus fixture packages (`pkg_base`, `pkg_cmake_1`, `pkg_meson_1`, etc.)
- `pkgaux/` — nox helper utilities and requirements files
- `noxfile.py` — orchestrates prepare/test/report sessions; coverage data lands in `tmp/`

### Core modules

| Module | Role |
|---|---|
| `backend.py` | PEP-517 hooks (`build_wheel`, `build_sdist`, `get_requires_for_build_*`, `prepare_metadata_for_build_editable`) |
| `pyproj.py` | `PyProjBase` — central build-system object, holds parsed config and drives prep/build/copy |
| `pptoml.py` | Parses and validates the `[tool.pyproj.*]` sections of `pyproject.toml` |
| `validate.py` | Schema validation primitives (`valid`, `valid_dict`, `validating`, `ValidationError`) used pervasively |
| `norms.py` | Low-level normalisation helpers (paths, booleans, hashes, encodings) |
| `pep.py` | PEP-compliant name/version/tag normalisation and `CompatibilityTags` |
| `template.py` | `${...}` template substitution engine used in build target paths/options |
| `path/` | gitignore-style path matching (`PathMatcher`, `PathFilter`) and directory scanning |
| `dist_file/` | Distribution writers: `dist_targz` (sdist), `dist_zip`/`dist_binary_wheel` (wheel), `dist_copy` (file-copy logic) |
| `pkginfo.py` | `PkgInfo` — assembles the `METADATA` / `PKG-INFO` file |
| `builder/` | Third-party build integrations: `meson`, `cmake`, `process`, `download` |
| `load_module.py` | Entry-point loader (`EntryPoint`) used to resolve prep hooks and builder callables |
| `cli/` | `partis-pyproj` CLI (`__main__.py`, `init_pyproj.py`, `build_pyproj.py`) |

### Key data flow

1. A frontend (`pip`, `build`) calls a PEP-517 hook in `backend.py`.
2. `backend_init()` reads `pyproject.toml`, constructs a `PyProjBase` instance, and runs `tool.pyproj.prep` hook.
3. `PyProjBase` runs build targets (`tool.pyproj.targets`) sequentially via `Builder`.
4. `dist_copy` iterates source files through `PathFilter` (gitignore patterns) and writes them into the distribution via `dist_targz` or `dist_binary_wheel`.

### Test fixture packages
`tests/pkg_base`, `tests/pkg_cmake_1`, etc. are minimal `pyproject.toml` projects used by the integration tests. Tests that build wheels or sdists install the `partis-pyproj` sdist from `dist/` (built during `prepare`), which is why `nox -s prepare` must run first.

### Coverage
Coverage is gathered across subprocess boundaries using a `sitecustom` hook (`tests/cov_sitecustom`). Coverage files accumulate in `tmp/` with per-session names; `nox -s report` combines them.
