# partis-pyproj — Design Specification

This document describes the design intent, architectural invariants, and correctness
constraints for `partis.pyproj`, a minimal PEP-517 build back-end. It is intended
as a stable reference against which any implementation change can be evaluated.

---

## 1. Guiding Principles

These principles are non-negotiable. Any code that violates them is a bug,
regardless of whether it produces a working artifact.

1. **Stateless and structure-agnostic.** The backend must never inspect package
   contents to infer desired behaviour. All behaviour derives from explicit
   configuration in `pyproject.toml`.

2. **Maximal user control.** Every stage of distribution preparation — prep,
   build, copy — must be configurable. The backend must not silently add, remove,
   or reorder files beyond what is documented.

3. **Single source of truth.** All configuration lives in `pyproject.toml`
   under `[tool.pyproj.*]`. No environment variable, CLI flag, or implicit
   convention may override it unless the mechanism is explicitly documented
   (e.g. `PYPROJ_LOG_LEVEL`, `config_settings`).

4. **A distribution is a collection of files plus metadata.** Nothing more.
   The backend must not inject runtime dependencies, modify source files, or
   alter the logical content of what the user declared.

---

## 2. PEP Compliance

The backend must conform to the following PEPs. A deviation from any of these
in the implementation is a defect.

| PEP | Scope |
|-----|-------|
| [PEP 517](https://peps.python.org/pep-0517/) | Build back-end interface: `build_wheel`, `build_sdist`, `get_requires_for_build_*` |
| [PEP 621](https://peps.python.org/pep-0621/) | `[project]` table parsing and `project.dynamic` delegation to `tool.pyproj.prep` |
| [PEP 660](https://peps.python.org/pep-0660/) | Editable installs via `build_editable`, `prepare_metadata_for_build_editable` |
| [PEP 425](https://peps.python.org/pep-0425/) | Compatibility tags for binary distributions |
| [PEP 508](https://peps.python.org/pep-0508/) | Environment markers in `target.enabled` |
| [PEP 685](https://peps.python.org/pep-0685/) | `extra` name normalisation |
| [PEP 735](https://peps.python.org/pep-0735/) | `[dependency-groups]` support |

---

## 3. Architecture

### 3.1 Module Responsibilities

Each module has a single, well-defined role. Cross-cutting concerns (validation,
path normalisation) are factored into shared primitives.

| Module | Responsibility | Must NOT |
|--------|---------------|----------|
| `backend.py` | PEP-517 hook entry points | contain build logic |
| `pyproj.py` (`PyProjBase`) | Central build-system object; drives prep→build→copy | perform I/O except through `dist_file` and `builder` |
| `pptoml.py` | Parse and validate `[tool.pyproj.*]` | silently coerce invalid config |
| `validate.py` | Schema validation primitives | raise bare exceptions; must use `ValidationError` |
| `norms.py` | Path, boolean, hash, encoding normalisation | depend on higher-level modules |
| `pep.py` | PEP-compliant name/version/tag normalisation | deviate from the referenced PEP text |
| `template.py` | `${...}` substitution engine | evaluate templates more than once per value |
| `path/` | gitignore-style matching and directory scanning | follow symlinks outside the project root |
| `dist_file/` | Distribution writers (sdist tar.gz, wheel zip, file copy) | modify file content during copy |
| `pkginfo.py` | Assemble `METADATA` / `PKG-INFO` | invent fields not in the project table |
| `builder/` | Third-party integrations (meson, cmake, process, download) | write outside `build_dir` or `prefix` |
| `load_module.py` | Entry-point resolution | execute code at import time |
| `cli/` | CLI commands (`init`, `build`, `prep`, `rebuild`) | bypass `PyProjBase`; must use the same hooks as PEP-517 |

### 3.2 Data Flow

The canonical execution order for any distribution build:

```
Frontend (pip, build, etc.)
  │
  ▼
backend.py  ──  PEP-517 hook
  │
  ├─ backend_init()
  │    ├─ read pyproject.toml  →  pptoml.py (parse + validate)
  │    ├─ construct PyProjBase
  │    └─ run tool.pyproj.prep hook
  │
  ├─ tool.pyproj.dist.prep          (both sdist and wheel)
  ├─ tool.pyproj.dist.source.prep   (sdist only)
  ├─ tool.pyproj.targets            (sequential, in order)
  ├─ tool.pyproj.dist.binary.prep   (wheel only, after all targets)
  │
  └─ dist_copy  →  PathFilter  →  dist_targz | dist_binary_wheel
```

**Invariants of this flow:**

- Prep hooks execute before any file copying.
- Build targets execute strictly sequentially, in declared order.
- A failing target aborts the entire build; later targets must not run.
- `dist_copy` sees only the final filesystem state after all targets complete.
- `pyproject.toml`, `project.readme`, and `project.license` are
  **always** included in sdist output, even if not listed in `copy`.

---

## 4. Correctness Constraints

These are specific, testable invariants. A reviewer finding code that violates
any of them should flag it as a bug.

### 4.1 Copy Semantics

- Every `src` must resolve within the project root. Paths escaping the root are errors.
- If `src` is a directory, copying is recursive and respects ignore patterns.
- If `src` is a single file explicitly listed, it is copied even if it matches an ignore pattern.
- Ignore patterns without a path separator match **basenames** (`foo` ≡ `**/foo`).
  Patterns with a separator match **full relative paths**.
- Ignore patterns are inherited: `dist` → `dist.source`/`dist.binary` → individual copy ops.
- Multiple include rules mapping to the same destination file must raise an error (no silent overwrites).
- On case-insensitive filesystems, distinct sources mapping to the same normalised
  destination must raise a collision error.
- `glob` with `**` must **not** match directories — only files.
- `strip` removes up to N leading path components from the relative source path.
- Symlinks in sdist: resolved within the project root are preserved as relative links.
  Links outside the root or dangling links are errors.
- Wheels do not support symlinks; links are expanded in place.

### 4.2 Validation

- All `tool.pyproj.*` input must pass through `validate.py` primitives.
- Invalid configuration must raise `ValidationError` before any build hooks execute.
- `config_settings` keys not declared in `tool.pyproj.config` must be rejected.
- `config_settings` values of the wrong type must be rejected.
- `tool.pyproj.config` must not contain nested tables.
- Boolean `config_settings` are parsed from a fixed set of known strings; anything
  else is an error.
- Enumerated config options (single-level list values) use the first item as the default
  and reject values not in the list.

### 4.3 Template Substitution

- Templates use `${...}` syntax only; bare `$identifier` is explicitly unsupported.
- `$$` is a literal `$` escape.
- Substitutions are processed once, in declaration order. No static analysis or
  re-evaluation.
- If a substitution contains path separators, the result must be converted to
  platform-specific format and resolved relative to the project directory.
- The template namespace must include: `root`, `tmpdir`, `pptoml`, `project`,
  `pyproj`, `config_settings`, `targets`, per-target values (`work_dir`,
  `src_dir`, `build_dir`, `prefix`, `env`, `options`), and `config_vars`.

### 4.4 Builder Contracts

- Builders receive: `backend`, `logger`, `options`, `work_dir`, `src_dir`,
  `build_dir`, `prefix`, `setup_args`, `compile_args`, `install_args`,
  `build_clean`, `runner`.
- `build_clean` defaults to `False`.
- Builders must not write outside `build_dir` or `prefix`.
- `tmpdir` is destroyed before the distribution is assembled; files needed in the
  distribution must be copied back into the project tree by the target.
- The `download` builder must verify HTTP status codes and handle empty files.
  Checksum verification is mandatory when a checksum is declared.

### 4.5 Editable Installs

- Editable installs must support pure Python packages, compiled extensions, and
  package data.
- Source/data changes take effect on next interpreter run without reinstalling.
- New files and directories require reinstallation.
- Compiled extensions are **not** automatically recompiled; `partis-pyproj rebuild`
  triggers this.
- The staging directory is in-tree at `{build_dir}/{name}_{version}_{py_version}`,
  where `build_dir` is `tool.pyproj.editable.build_dir` (default `build/editable`)
  and must resolve within the project root, but not to the project root itself.
  In-tree because the path is keyed on the source tree: two checkouts of the same
  package and version must not share (and clobber) one staging directory.
  The install target venv is not observable from a PEP 517 backend, so two venvs
  installing the *same* tree still share one staging directory.
- A dedicated venv in the staging directory is used for rebuilds, independent of
  build isolation.

### 4.6 Self-Hosting

The repository uses its own backend (`build-backend = "pyproj.backend"`,
`backend-path = ['src']`) to build itself. Any change that breaks the backend
also breaks the ability to build and release the project.

---

## 5. Version History Summary

Key behavioural changes across releases, for context when reviewing
whether current code matches documented intent.

| Version | Notable Change |
|---------|---------------|
| v0.2.2 | Python 3.14 support; `config` key normalisation fix (`_` vs `-`); `build_clean` defaults to `False`; CLI split (`prep` / `rebuild`) |
| v0.2.1 | PEP 660 editable installs; incremental rebuilds; CLI `init` and `build`; stricter type validation |
| v0.2.0 | PEP 685 extra names; PEP 735 dependency groups; `glob` no longer matches directories; download verification |
| v0.1.9 | Fix config vs config_settings value comparison |
| v0.1.7 | `download` builder with caching and extraction |
| v0.1.5 | Template variable substitutions; pypy support; Windows path fixes |
| v0.1.4 | `process` builder; wheel record CSV fix |
| v0.1.0 | Generalised `tool.pyproj.targets`; meson/cmake builders; pathlib migration |

---

## 6. Test Strategy

- Tests live in `tests/` with fixture packages (`pkg_base`, `pkg_cmake_1`, `pkg_meson_1`, etc.).
- Integration tests build wheels/sdists by installing the `partis-pyproj` sdist from
  `dist/`, so `nox -s prepare` must run first.
- Coverage spans subprocess boundaries via a `sitecustom` hook in `tests/cov_sitecustom`.
- Any change to core modules must not break the existing fixture builds.
