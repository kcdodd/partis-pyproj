[![tests](https://github.com/kcdodd/partis-pyproj/actions/workflows/tests.yaml/badge.svg)](https://github.com/kcdodd/partis-pyproj/actions/workflows/tests.yaml)

The ``partis.pyproj`` package aims to be a minimal and
transparent implementation of a [PEP-517](https://www.python.org/dev/peps/pep-0517) build back-end.
The guiding principles adopted for ``partis.pyproj`` are:

* Stateless and agnostic to project structure and management, focused on the
  stages of preparing a distribution.
* Avoid inspecting or inferring "desired behavior" from the contents of the package
  being distributed / installed, and provide as much control as possible over the
  entire process.
* All configuration of ``partis.pyproj`` contained in ``pyproject.toml``
* A distribution is simply a collection of files,
  plus package meta-data for either source or binary (wheel) distribution formats.

### Quickstart

Below is a minimal example project structure for a pure Python package
named `myproj`, and backend configuration in `pyproject.toml` to build
source and binary (wheel) distributions for installation:

- `src/myproj/__init__.py`
- `tests/test_everything.py`
- `LICENSE.txt`
- `pyproject.toml`
- `README.md`


```toml
# pyproject.toml
[project]
name = "myproj"
description = "Project myproj"
version = "0.0.1"
readme = { file = "README.md" }
license = { file = "LICENSE.txt" }
dependencies = ['typing-extensions']

[dependency-groups]
test = ['pytest']

[build-system]
requires = ["partis-pyproj"]
# point the frontend to the backend partis-pyproj
build-backend = "partis.pyproj.backend"

# configure the backend
[tool.pyproj.dist]
# patterns to ignore for both source and wheel distributions
ignore = ['__pycache__', '*.py[cod]', '*.so', '*.egg-info', '.nox', '.pytest_cache', '.coverage']

[tool.pyproj.dist.source]
# copy everything needed to re-distribute the source code (pyproject.toml, readme, and license are added automatically)
copy = ["src", "tests"]

[tool.pyproj.dist.binary.purelib]
# copy how it should appear installed in site-packages
copy = [{ src = "src/myproj", dst = "myproj" }]
```

The process of building a source or binary distribution is broken down into
three general stages:

- **prepare** - Actions required to start the process of creating a distribution.
  The 'prep' may be any custom function the developer wants to occur before files
  are copied into the distribution, such as filling in dynamic metadata.
- **build** - If needed, running one or more build stages using third-party
  or custom methods. ``partis.pyproj`` provides some standard structure to this
  configuration, but otherwise avoids taking on the responsibility of a full build system.
- **copy** - Copy files into the distribution.

Running `python -m build` (or `pip wheel .`, `pip install .`, etc.) executes the `prepare`, `build`,
and `copy` stages in order and writes the resulting sdist or wheel.
The sequence of actions for a distribution is roughly:

- `tool.pyproj.prep`: Run before anything else, used to fill in dynamic metadata or
  update to `build_requires` list for binary distributions (front-end to install build requirements).
- `tool.pyproj.dist.prep`: Run for both source and binary distributions to prepare
  or configure initial files.
- `tool.pyproj.dist.source.prep`: Runs before copying files to a source distribution.
- `tool.pyproj.targets`: Run build targets, in order, where `enabled` evaluates to true
  (conditions based on [environment markers](https://packaging.pypa.io/en/stable/markers.html)).
- `tool.pyproj.dist.binary.prep`: Run before copying files to a binary distribution
  (after all enabled build targets complete).
  Can also customize compatibility tags for the binary distribution as per [PEP 425](https://peps.python.org/pep-0425/).

### Copy Operations

The majority of ``partis.pyproj`` is devoted to copying files into a distribution.
This logic is the most complicated, but derives from a combination of existing
formats and behaviors.

**Source and destination**

* Each item listed in a `copy` is treated like `copyfile` or `copytree`, depending
  on whether the `src` is a file or a directory.
* All `src` must exist within the root of the project, any external or generated
  files must be prepared before the copy operation.
* If `src` is a directory, all files are copied recursively unless they
  match an ignore pattern for that distribution type.
* If an item is a single path, it is expanded as ``dst = src``.
* `dst` is relative, specifically depending on whether it is a source or binary (wheel)
  distribution and which install scheme is desired (`purelib`, `platlib`, etc.).
* Destination file paths are constructed from matched source paths roughly equivalent
  to `{scheme}/dst/match.relative_to(src)`.
* For source distributions, symlinks that resolve within the project root are preserved;
  links that point outside the tree or are dangling result in an error.
  Link targets copied into distributions are transformed so they are relative to
  its location.
* Wheels do not support symbolic links, and links are expanded in place leading
  to possible file duplication.
* Hidden files are treated like any other path unless ignored.
* Pattern matching uses POSIX-style `/` separators. On case-insensitive file
  systems (e.g. Windows) different source files that would map to the same
  destination path are considered collisions and abort the copy.
* If multiple include rules map to the same destination file, the backend raises
  an error to avoid silent overwrites.

**Include patterns**

* An include list is used to filter files or directories to be copied, expanded
  to zero or more matches relative to `src`.
* `glob` follows the format of [Path.glob](https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob).
  If recursive pattern `**` is used, the glob will *not* match directories,
  since the resulting `copytree` would end up copying all files in the directory.
* `rematch` may further discriminate filenames (already matched by `glob`) using [Regular Expression Syntax](https://docs.python.org/3/library/re.html#regular-expression-syntax). Directories are *not* considered by `rematch`.
* `replace` can  change destination *filenames* using
  [Format String Syntax](https://docs.python.org/3/library/string.html#format-string-syntax), with values supplied by any groups defined in `rematch`.
  This cannot rename directories.
* `strip` can remove (up to) the given number of path components from the relative
  `src` path.

  For example,

  ```toml
  include = [{ glob = "src/**/*.py", rematch = "src/(.*)", replace = "{0}", strip = 1 }]
  ```

  copies `src/pkg/mod.py` into the destination as `pkg/mod.py`.

**Ignore patterns**

* An `ignore` list follows the format of [git-ignore](https://git-scm.com/docs/gitignore#_pattern_format).
* Individual *files* explicitly listed as a `src` will be copied, even if it
  matches one of the `ignore` patterns.
* The `ignore` patterns may be specified at different levels of distributions in
  ``tool.pyproj.dist``, ``tool.pyproj.dist.source``, ``tool.pyproj.dist.binary``,or individual copy operations ``{ src = '...', dst = '...', ignore = [...] }``.
  The ignore patterns are inherited at each level of specificity.
* If an ignore pattern **does not contain** any path separators, it is matched to
  the **base-name** of every file or directory being considered (E.G. `foo` is
  equivalent to ``**/foo``).
* If an ignore pattern **does contain** a path separator, then it is matched to the
  **full path** relative to either the project root (for distribution-level ignores)
  or `src` (for copy-level ignores).


Individual copy operations have the following structure, but there are also
shorthands where the rest are default. A semi-formal description of this configuration follows:

```
  copy: copy_item | array{copy_item}
  copy_item: PATH | table{"src =" PATH, "dst =" PATH?, "include =" include?, "ignore =" ignore?}
  include: GLOB | array{include_item}
  include_item: GLOB | table{"glob =" GLOB, "rematch =" REGEX?, "replace =" FORMAT?}
  ignore: IGNORE | array{IGNORE}

  PATH: < POSIX path, implicitly relative to project root >
  GLOB: < https://docs.python.org/3/library/glob.html#glob.glob >
  REGEX: < https://docs.python.org/3/library/re.html#regular-expression-syntax >
  FORMAT: < https://docs.python.org/3/library/string.html#formatstrings >
  IGNORE: < https://git-scm.com/docs/gitignore#_pattern_format >
```


The source distribution will automatically contain `pyproject.toml`, `project.readme.file`,
and `project.license.file` (if given) even if they are not explicitly listed
in `tool.pyproj.dist.source.copy`.


**Example**

```toml
# pyproject.toml
[tool.pyproj.dist]
ignore = [
  '__pycache__',
  'doc/_build' ]

[tool.pyproj.dist.source]

ignore = [
  '*.so' ]

copy = [
  'src',
  'doc']

[[tool.pyproj.dist.binary.purelib.copy]]
src = 'src/my_project'
include = '**/*.py'
dst = 'my_project'
ignore = [
  'bad_file.py',
  './config_file.py']

[[tool.pyproj.dist.binary.platlib.copy]]
src = 'src/my_project'
include = '**/*.so'
dst = 'my_project'
```


##### Source Distribution (``.tar.gz``)

| Result | File Path |
|--------|-----------|
| **Included**       | ``pyproject.toml``                                |
| **Included**       | ``doc/index.rst``                                 |
| **Included**       | ``src/my_project/__init__.py``                    |
| **Included**       | ``src/doc/_build``                                |
| *Ignored*          | ``doc/_build``                                    |
| *Ignored*          | ``doc/__pycache__``                               |
| *Ignored*          | `__pycache__`                                   |
| *Ignored*          | ``src/__pycache__``                               |
| *Ignored*          | ``src/my_project/mylib.so``                       |


##### Binary Distribution (``.whl``)

| Result | File Path |
|--------|-----------|
| **Included**       | ``src/my_project/__init__.py``                    |
| **Included**       | ``src/my_project/sub_dir/__init__.py``            |
| **Included**       | ``src/my_project/sub_dir/config_file.py``         |
| **Included**       | ``src/my_project/mylib.so``                       |
| *Ignored*          | ``src/my_project/bad_file.py``                    |
| *Ignored*          | ``src/my_project/config_file.py``                 |
| *Ignored*          | ``src/my_project/sub_dir/bad_file.py``            |


Preparation Hooks
-----------------

The backend provides a mechanism to perform an arbitrary operation before any
files are copied into either the source or binary distribution:

Each hook must be a python module (a directory with an
``__init__.py`` file), either directly importable or relative to the 'pyproject.toml'.
The hook is specified according to the `entry_points` specification, and
must resolve to a function that takes the instance of the build system and
a logger.
Keyword arguments may also be defined to be passed to the function,
configured in the same section of the 'pyproject.toml'.

```toml
# pyproject.toml
[tool.pyproj.dist.binary.prep]
# hook defined in a python module
entry = "a_custom_prep_module:a_prep_function"

[tool.pyproj.dist.binary.prep.kwargs]
# define keyword argument values to be passed to the pre-processing hook
a_custom_argument = 'some value'
```

This will be treated by the backend **equivalent to the
following code** run from the `pyproject.toml` directory:

```python
# equivalent backend
import a_custom_prep_module

a_custom_prep_module.a_prep_function(
  backend,
  logger,
  a_custom_argument = 'some value' )
```

> :warning: Only those requirements listed in `build-system.requires`
> will be importable during `tool.pyproj.prep`, and only those added to
> `backend.build_requires` will be available in subsequent hooks.

Dynamic Metadata
----------------

As described in [PEP-621](https://www.python.org/dev/peps/pep-0621), field values in the `project` table may be deferred
to the backend by listing the keys in `project.dynamic`, which must be set by the `tool.pyproj.prep` processing hook.

```toml
# pyproject.toml
[project]
name = "my_pkg"
dynamic = ["version"]

[tool.pyproj.prep]
entry = "pkgaux:prep"
```

The hook should set values for all keys of the `project` table listed
in ``project.dynamic``.

```python
def prep( backend, logger ):
  backend.project.version = "1.2.3"
```

#### Build Targets

Methods of compiling extensions (or anything else) is delegated to third-party
build systems specified in the 'pyproject.toml' array ``tool.pyproj.targets``.
This means that, unlike with setuptools, detailed configuration of the build itself
would likely be stored in separate files like ``meson.build`` with Meson,
or ``CMakeLists.txt`` with CMake.

In case different options are needed depending on the environment, the `enabled`
field can be a [PEP-508](https://www.python.org/dev/peps/pep-0508) [environment marker](https://packaging.pypa.io/en/stable/markers.html),
or can also be set manually (True/False) by an earlier 'prep' stage.
Each third-party build system is given by the `entry`, which is an entry-point
to a function that takes in the arguments and options given in the table
for that build.

**standard config**
```
entry: ENTRY_POINT           # entry-point specification of builder to use
work_dir: PATH               # directory from which the builder will be run
src_dir: PATH                # directory of source code
build_dir: PATH              # directory for temporary build files (cleaned on exit)
prefix: PATH                 # directory which distribution files should be staged (cleaned on exit)
setup_args: array{STRING}    # 3-stage build
compile_args: array{STRING}  # 3-stage build
install_args: array{STRING}  # 3-stage build
options: table{STRING|BOOL}? # options passed to builder from pyproject.toml
env: table{STRING|STRING}?   # environment variables to set
build_clean: BOOL?           # control cleanup (ie for development builds)
enabled: (BOOL|MARKER)?      # environment marker
```

Targets are executed sequentially. If a target fails or its entry point cannot
be resolved, the remaining targets are skipped and the build aborts with an
error message. Parallel execution is intentionally unsupported to keep ordering
and cleanup deterministic.

There are several entry points available as-is:

- `partis.pyproj.builder:meson` - Support for [Meson Build system](https://mesonbuild.com/)  with the 'extra' ``partis-pyproj[meson]``
- `partis.pyproj.builder:cmake` - Support for [CMake](https://cmake.org/) with the 'extra' ``partis-pyproj[cmake]``
- `partis.pyproj.builder:process` - Support for running arbitrary command line executable
- `partis.pyproj.builder:download` - Support for downloading a file to `build_dir`


Options for `partis.pyproj.builder:download`:

```
[tool.pyproj.targets.options]
url: URL
checksum: ALG=HEX     # expected checksum
filename: STRING?     # rename in build_dir, defaults to mangled version of url
extract: BOOL?        # extract/decompress as a tar file
executable: BOOL?     # set execute permission
```

Checksum `ALG` can be `sha256`, `md5`, or another algorithm in [hashlib](https://docs.python.org/3/library/hashlib.html)

**Example**

In this example, the source directory must contain appropriate `meson.build` files,
since the 'pyproject.toml' configuration only provides a way of running
``meson setup`` and ``meson compile``.


```toml
# pyproject.toml
[[tool.pyproj.targets]]

entry = 'partis.pyproj.builder:meson'

# location to create temporary build files (optional)
build_dir = 'tmp/build'
# location to place final build targets
prefix = 'tmp/prefix'

[tool.pyproj.targets.options]
# Custom build options (e.g. passing to meson -Dcustom_feature=enabled)
custom_feature = 'enabled'

[tool.pyproj.dist.binary.platlib]
# binary distribution platform specific install path
copy = [
  { src = 'tmp/prefix/lib', dst = 'my_project' } ]
```

The `src_dir` and `prefix` paths are always relative to the project
root directory, and default to ``src_dir = '.'`` and ``prefix = './build'``.
Currently these must all be a sub-directory relative to the 'pyproject.toml'
(e.g. a specified temporary directory).

The result should be equivalent to running the following commands in a custom
defined builder:

```python

def custom_builder(
  backend,
  logger: logging.Logger,
  options: dict,
  work_dir: Path,
  src_dir: Path,
  build_dir: Path,
  prefix: Path,
  setup_args: list[str],
  compile_args: list[str],
  install_args: list[str],
  build_clean: bool,
  runner: ProcessRunner):

  runner.run(['meson', 'setup', *setup_args, '--prefix', prefix, build_dir src_dir])
  runner.run(['meson', 'compile', *compile_args, '-C', build_dir])
  runner.run(['meson', 'install', *install_args, '-C', build_dir])
```

All files in 'build/lib' are then copied into the binary distribution's 'platlib' install path.

A custom 'builder' for the entry-point can also be used, and is simply a callable
with the correct signature.

**Template substitution**

The paths and options in build targets may contain template substitutions to more
easily pass environment-dependent information to the third-party build system.
The substitution rule is specialized to `partis-pyproj`, but derives from
Python [Template string](https://docs.python.org/3/library/string.html#template-strings) with additions to support nested identifiers and construction of paths. The commonality is:

- `$$` is an escape; it is replaced with a single `$`.
- `${identifier}` names a substitution placeholder matching a mapping key of "identifier".

However, `$identifier` (without braces) is *not supported*, but this restriction allows more expressive substitutions.

```
substitution: "${" (variable|literal|SEP)+ "}"
variable: IDENTIFIER ("." IDENTIFIER | "[" INTEGER "]")*
SEP: "/"
literal: "'" CHAR+ "'"
IDENTIFIER: < python identifier >
INTEGER: < integer >
CHAR: < ascii alpha-numeric, dot ".", dash "-", underscore "_" >
```

Top-level template variable identifiers can reference the content of the original 'pyproject.toml', config. settings, environment variables, and values already substituted in the build target or earlier targets.
If the substitution contains any separators the result is interpreted as a path, converted to platform-specific filesystem format, and resolved to project directory.
The template namespace contains the following keys:

- `root`: Absolute path to project root directory
- `tmpdir`: A temporary directory created and shared by all build targets.
  This directory is removed before the distribution is created, so any needed files must be copied back to a location within the project tree by one of the targets
  (eg. the "install" step of 3-stage builds with a `prefix` within the project).
- `pptoml`: Top-level of parsed `pyproject.toml`
- `project`: The `project` section, including `name`, `version`, etc.
- `pyproj`: The `tool.pyproj` section.
- `config_settings`: A mapping from the `config_settings` passed to backend per PEP-517
  after defaults applied from `tool.pyproj.config` (described below).
- `targets`': List from `tool.pyproj.targets`, updated as targets are processed.
- `work_dir`, `src_dir`, `build_dir`, `prefix`: Per-target values (if processed before the substitution)
- `env`: Defaults to `os.environ`, or per-target value from `tool.pyproj.targets.env`
  (if processed before the substitution).
- `options`: Per-target value from `tool.pyproj.targets.options` (if processed before the substitution)

Template substitutions are processed (once) in the *order in which they appear* from the `pyproject.toml`, no static analysis is performed. It is up to the developer to put them in the needed order if one template references a value resulting from another template.
In the example below, the value of `options.some_option` would be substituted with a filesystem equivalent path for `{root}/build/something/my_pkg/xyz/abc.so`:


```toml
# pyproject.toml
[project]
name = "my_pkg"

[[tool.pyproj.targets]]
prefix = "build/something"
options = {some_option = "${prefix/project.name/'xyz'/'abc.so'}"}
```

Binary distribution install paths
---------------------------------

If there are some binary distribution files that need to be installed to a
location according to a local installation scheme
these can be specified within sub-tables.
Available install scheme keys, and **example** corresponding install locations, are:

- `purelib` ("pure" library Python path): ``{venv}/lib/python{X}.{Y}/site-packages/``
- `platlib` (platform specific Python path): ``{venv}/lib{platform}/python{X}.{Y}/site-packages/``
  Both `purelib` and `platlib` install to the base 'site-packages'
  directory, so any files copied to these paths should be placed within a
  desired top-level package directory.

- `headers` (INCLUDE search paths): ``{venv}/include/{site}/python{X}.{Y}{abiflags}/{distname}/``
- `scripts` (executable search path): ``{venv}/bin/``
  Even though any files added to the `scripts` path will be installed to
  the `bin` directory, there is often an issue with the 'execute' permission
  being set correctly by the installer (e.g. `pip`).
  The only verified way of ensuring an executable in the 'bin' directory is to
  use the ``[project.scripts]`` section to add an entry point that will then
  run the desired executable as a sub-process.

- `data` (generic data path): ``{venv}/``

```toml
# pyproject.toml
[tool.pyproj.dist.binary.purelib]
copy = [
  { src = 'build/my_project.py', dst = 'my_project/my_project.py'} ]

[tool.pyproj.dist.binary.platlib]
copy = [
  { src = 'build/my_project.so', dst = 'my_project/my_project.so'} ]

[tool.pyproj.dist.binary.headers]
copy = [
  { src = 'build/header.hpp', dst = 'header.hpp' } ]

[tool.pyproj.dist.binary.scripts]
copy = [
  { src = 'build/script.py', dst = 'script.py'} ]

[tool.pyproj.dist.binary.data]
copy = [
  { src = 'build/data.dat', dst = 'data.dat' } ]
```

Config Settings
---------------

As described in [PEP-517](https://www.python.org/dev/peps/pep-0517),
an installer front-end may implement support for
passing additional options to the backend
(e.g. ``--config-settings`` in `pip`).
These options may be defined in the ``tool.pyproj.config`` table, which is used
to validate the allowed options, fill in default values, and cast to
desired types.
These settings, updated by any values passed from the front-end installer,
are available in any processing hook.
Combined with an entry-point `kwargs`, these can be used to keep all
conditional dependencies listed in ``pyproject.toml``.

Passing an option that is not declared in `tool.pyproj.config` or providing a
value of the wrong type results in a validation error before any build hooks are
executed.


The type is derived from the value parsed from ``pyproject.toml``.
For example, the value of `3` is parsed as an integer, while ``3.0`` is parsed
as a float.
Additionally, the ``tool.pyproj.config`` table may **not** contain nested tables,
since it must be able to map 1:1 with arguments passed on
the command line.
A single-level list may be set as a value to restrict the allowed value to
one of those in the list, with the first item in the list being used as the
default value.

Boolean values passed to ``--config-settings`` are parsed by comparing to
string values ``['true', 'True', 'yes', 'y', 'enable', 'enabled']``
or ``['false', 'False', 'no', 'n', 'disable', 'disabled']``.

```toml

[tool.pyproj.config]
a_cfg_option = false
another_option = ["foo", "bar"]

[tool.pyproj.prep]
entry = "pkgaux:prep"
kwargs = { deps = ["additional_build_dep >= 1.2.3"] }
```

```python
# pkgaux/__init__.py

def prep( backend, logger, deps ):

  if backend.config_settings.a_cfg_option:
    backend.build_requires |= set(deps)

  if backend.config_settings.another_option == 'foo':
    ...

  elif backend.config_settings.another_option == 'bar':
    ...
```

In this example, the command
``pip install --config-settings a_cfg_option=true ...`` will cause the
'additional_build_dep' to be installed before the build occurs.
The value of `another_option` may be either `foo` or `bar`,
and all other values will raise an exception before reaching the entry-point.

