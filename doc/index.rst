
Packaging (:mod:`partis.pyproj`)
================================

The :mod:`partis.pyproj <partis.pyproj>` package aims to be very simple and
transparent implementation of a :pep:`517` build back-end.

* does not attempt to inspect anything from the contents of the package
  being distributed / installed
* relies on an understanding that a distribution is simply a collection of files
  including package meta-data written in particular formats.
* back-end implementation strives to be compliant with all relevant
  specifications.


While the :pep:`517` standard describes the outward interface to a general
build backend, it does not restrict how the backend should be configured.
The approach to configuration options is to make them similar to operations
available in the standard library.
For example, specifying what is included in a distribution is modeled on
file manipulation routines from the
:mod:`shutil` module, where the destination of the
operation is into a distribution file ( ``*.tar.gz`` or ``*.whl`` ).
However, the backend handles tracking of added files to build the wheel
manifest.

The process of building a source or binary distribution is broken down into
a 'prep' stage followed by 'copy' stage.
The 'prep' may be any custom function the developer wants to occur before files
are copied into the distribution, such as filling in dynamic metadata,
or generating files.
However, running another build program should be performed in the 'targets' stage
(see :ref:`build_targets`), which is run only for binary distributinos and handles
some checking/cleanup of build directories.

The 'copy' operation is specified by a sequence of find-filter-copy pattern based
rules. Instead of using a ``MANIFEST.in`` file or ``find_packages`` routine,
this gives full control within the ``pyproject.toml`` file over what goes into
the distribution and where it ends up.

The overall sequence of actions for a distribution is:

* ``tool.pyproj.prep`` : called to fill in 'dynamic' metadata, or update
  the 'build_requires' list of requirements needed to build a binary distribution.
* ``tool.pyproj.dist.prep``: called first for both source or binary distributions.
  Can be used to prepare or configure files.
* ``tool.pyproj.dist.source.prep``: called before copying files to a source distribution.
* ``tool.pyproj.targets``: Run any targets where ``enabled`` evaluates to true.
  This is only used for compiling extensions (see :ref:`build_targets`).
* ``tool.pyproj.dist.binary.prep``: called before copying files to a binary distribution.

  .. note::

    The ``tool.pyproj.dist.binary.prep`` hook may also be used to
    customize the compatibility tags for the binary distribution
    (according to :pep:`425`) as a list of tuples
    ``( py_tag, abi_tag, plat_tag )`` assigned to
    the ``compat_tags`` key of
    :py:obj:`PyProjBase.binary <partis.pyproj.pyproj.PyProjBase.binary>`.

    If no tags are returned from the hook, the default tags
    will be used for the current Python interpreter if any files are copied to
    the ``platlib`` install path.
    Otherwise, ``[( 'py{X}', 'none', 'any' )]`` is the default.

Copy Operations
---------------

.. code-block:: EBNF
  :caption: copy operation

  copy: copy_item | listof{copy_item}
  copy_item: PATH | dict{src = PATH, dst = PATH?, include = include?, ignore = ignore?}
  include: GLOB | listof{include_item}
  include_item: GLOB | dict{glob = GLOB, rematch = REGEX?, replace = FORMAT?}
  ignore: IGNORE | listof{IGNORE}

  PATH: < POSIX path, implicitly relative to project root >
  GLOB: < https://docs.python.org/3/library/glob.html#glob.glob >
  REGEX: < https://docs.python.org/3/library/re.html#regular-expression-syntax >
  FORMAT: < https://docs.python.org/3/library/string.html#formatstrings >
  IGNORE: < https://git-scm.com/docs/gitignore#_pattern_format >


.. rubric:: Copy source and destination

* Each item listed in ``copy`` for a distribution is treated like :func:`shutil.copyfile`
  or :func:`shutil.copytree`, depending on whether the ``src`` is a file or a directory.
* All ``src`` must existing within the root of the project, any external files
  must be prepared separately from the copy operation.
* If ``src`` is a directory, all files are copied recursively unless they
  match an ignore pattern for the distribution type.
* The ``dst`` is relative to a distribution archive base directory, specifically
  depending on whether it is a source or binary (wheel) distribution.
* If the item is a single path, it is expanded as ``dst = src``.

.. rubric:: Include patterns

* An ``include`` list is used to filter files or directories to be copied, expanded
  to zero or more matches relative to ``src``.
* ``glob`` follows the format of :mod:`glob`, supporting recursive ``**``.
* The destination path is constructed from the matched source path taken relative to
  ``src`` and joined with ``dst``.
* ``rematch`` may further discriminate files by regular expression
  following the format of Python :mod:`re` (must already be matched by ``glob``).
* ``replace`` may be used to alter the destination filename following
  :meth:`~string.format`, with values supplied by any groups defined in ``rematch``.


.. rubric:: Ignore patterns

* An ``ignore`` list follows the format of git-ignore, https://git-scm.com/docs/gitignore#_pattern_format.
* Individual *files* explicitly listed as a ``src`` will be copied, even if it
  matches one of the ``ignore`` patterns.
* The ``ignore`` patterns may be specified at different levels of distributions in
  ``tool.pyproj.dist``, specifically for ``tool.pyproj.dist.binary`` or
  ``tool.pyproj.dist.source``, or individually for each copy operation
  ``{ src = '...', dst = '...', ignore = [...] }``.
  The ignore patterns are inherited at each level of specificity.
* If an ignore pattern **does not** contain any path separators, it is matched to
  the **base-name** of every file or directory being considered (E.G. ``foo`` is
  equivalent to ``**/foo``).
* If an ignore pattern does **contain** a path separator, then it is matched to the
  **full path** relative to either the project root (for distribution-level ignores)
  or ``src`` (for copy-level ignores).



.. code-block:: toml
  :caption: ``pyproject.toml``

  [project]
  # required project metadata
  name = "my-project"
  version = "1.0"

  [build-system]
  # specify this package as a build dependency
  requires = [
    "partis-pyproj" ]

  # direct the installer to the PEP-517 backend
  build-backend = "partis.pyproj.backend"

  [tool.pyproj.dist]
  # define patterns of files to ignore for any type of distribution
  ignore = [
    '__pycache__',
    '*.py[cod]',
    '*.so',
    '*.egg-info' ]

  [tool.pyproj.dist.source]
  # define what files/directories should be copied into a source distribution
  copy = [
    'src',
    'pyproject.toml' ]

  [tool.pyproj.dist.binary.purelib]
  # define what files/directories should be copied into a binary distribution
  # the 'dst' will correspond to the location of the file in 'site-packages'
  copy = [
    { src = 'src/my_project', dst = 'my_project' } ]

A short example of what what paths would be included or ignored based on the
above ``pyproject.toml``:

.. code-block:: toml

  [tool.pyproj.dist]
  ignore = [
    '__pycache__',
    'doc/_build' ]

  [tool.pyproj.dist.source]

  ignore = [
    '*.so' ]

  copy = [
    'src',
    'doc',
    'pyproject.toml' ]

  [[tool.pyproj.dist.binary.purelib.copy]]
  src = 'src/my_project'
  glob = '**/*.py'
  dst = 'my_project'
  ignore = [
    'bad_file.py'
    './config_file.py']

  [[tool.pyproj.dist.binary.platlib.copy]]
  src = 'src/my_project'
  glob = '**/*.so'
  dst = 'my_project'


.. tabularcolumns:: |p{3cm}|p{3cm}|p{9cm}|

.. table:: Resulting inclusion or ignore rule for specific paths
  :widths: 20 60
  :class: longtable

  +--------------------+---------------------------------------------------+
  | Result             | File Path                                         |
  +====================+===================================================+
  | Source Distribution (``.tar.gz``)                                      |
  +--------------------+---------------------------------------------------+
  +--------------------+---------------------------------------------------+
  | **Included**       | ``pyproject.toml``                                |
  +--------------------+---------------------------------------------------+
  | **Included**       | ``doc/index.rst``                                 |
  +--------------------+---------------------------------------------------+
  | **Included**       | ``src/my_project/__init__.py``                    |
  +--------------------+---------------------------------------------------+
  | **Included**       | ``src/doc/_build``                                |
  +--------------------+---------------------------------------------------+
  | *Ignored*          | ``doc/_build``                                    |
  +--------------------+---------------------------------------------------+
  | *Ignored*          | ``doc/__pycache__``                               |
  +--------------------+---------------------------------------------------+
  | *Ignored*          | ``__pycache__``                                   |
  +--------------------+---------------------------------------------------+
  | *Ignored*          | ``src/__pycache__``                               |
  +--------------------+---------------------------------------------------+
  | *Ignored*          | ``src/my_project/mylib.so``                       |
  +--------------------+---------------------------------------------------+
  +--------------------+---------------------------------------------------+
  | Binary Distribution (``.whl``)                                         |
  +--------------------+---------------------------------------------------+
  +--------------------+---------------------------------------------------+
  | **Included**       | ``src/my_project/__init__.py``                    |
  +--------------------+---------------------------------------------------+
  | **Included**       | ``src/my_project/sub_dir/__init__.py``            |
  +--------------------+---------------------------------------------------+
  | **Included**       | ``src/my_project/sub_dir/config_file.py``         |
  +--------------------+---------------------------------------------------+
  | **Included**       | ``src/my_project/mylib.so``                       |
  +--------------------+---------------------------------------------------+
  | *Ignored*          | ``src/my_project/bad_file.py``                    |
  +--------------------+---------------------------------------------------+
  | *Ignored*          | ``src/my_project/config_file.py``                 |
  +--------------------+---------------------------------------------------+
  | *Ignored*          | ``src/my_project/sub_dir/bad_file.py``            |
  +--------------------+---------------------------------------------------+

Prep Processing Hooks
---------------------

The backend provides a mechanism to perform an arbitrary operation before any
files are copied into either the source or binary distribution:

Each hook must be a pure python module (a directory with an
``__init__.py`` file), either directly importable or relative to the 'pyproject.toml'.
The hook is specified according to the ``entry_points`` specification, and
must resolve to a function that takes the instance of the build system and
a logger.
Keyword arguments may also be defined to be passed to the function,
configured in the same section of the 'pyproject.toml'.

.. code-block:: toml

  [tool.pyproj.dist.binary.prep]
  # hook defined in a python module
  entry = "a_custom_prep_module:a_prep_function"

  [tool.pyproj.dist.binary.prep.kwargs]
  # define keyword argument values to be passed to the pre-processing hook
  a_custom_argument = 'some value'


This will be treated by the backend **equivalent to the
following code** run from the `pyproject.toml` directory:

.. code:: python

  import a_custom_prep_module

  a_custom_prep_module.a_prep_function(
    builder,
    logger,
    a_custom_argument = 'some value' )


The ``builder`` argument is an instance of
:class:`PyProjBase <partis.pyproj.pyproj.PyProjBase>`, and ``logger``
is an instance of :class:`logging.Logger`.

.. attention::

  Only those requirements listed in ``build-system.requires``
  will be importable by ``tool.pyproj.prep``, and only those added to
  :py:obj:`PyProjBase.build_requires <partis.pyproj.pyproj.PyProjBase.build_requires>`
  will be available in subsequent hooks.

Dynamic Metadata
----------------

As described in :pep:`621`, field values in the 'project' table may be deferred
to the backend by listing the keys in 'dynamic'.
If 'dynamic' is a non-empty list, the 'tool.pyproj.prep' processing hook must
be used to fill in the missing values.

.. code-block:: toml

  [project]
  dynamic = [
    "version" ]

  name = "my_pkg"

  ...

  [tool.pyproj.prep]
  entry = "pkgaux:prep"

The hook should set values for all keys of the ``project`` table listed
in ``project.dynamic``.

.. code-block:: python
  :caption: ``pkgaux/__init__.py``

  def prep( builder, logger ):
    builder.project.version = "1.2.3"


.. _build_targets:

Build Targets
-------------

The method of compiling extensions is delegated to a third-party build system,
such as Meson Build system https://mesonbuild.com/ or CMake https://cmake.org/,
both available on PyPI.
This means that, unlike with setuptools, detailed configuration of the build itself
would be given in separate files like ``meson.build`` with Meson,
or ``CMakeLists.txt`` with CMake.

This stage of the build process is specified in the 'pyproject.toml' array
``tool.pyproj.targets``.
Only one is needed, but it is possible to define more than one.
In case different options are needed depending on the environment, the ``enabled``
field can be a :pep:`508` environment :class:`Marker <packaging.markers.Marker>`,
or can also be set manually (True/False) by an earlier 'prep' stage.

Each third-party build system is given by the ``entry``, which is an entry-point
to a pure function that takes in the arguments and options given in the table
for that build.
The builtin functions for Meson or CMake simply format the options into command-line
arguments for the typical 'setup', 'compile', and 'install' steps.

* :func:`partis.pyproj.builder:meson <partis.pyproj.builder.meson.meson>`: With the 'extra' ``partis-pyproj[meson]``
* :func:`partis.pyproj.builder:cmake <partis.pyproj.builder.cmake.cmake>`: With the 'extra' ``partis-pyproj[cmake]``

A custom 'builder' for the entry-point can also be used, and is simply a callable
with the correct signature.
See one of the above builtin methods as an example.

For example, the following configuration,

.. code-block:: toml

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

To use this feature, the source directory must contain appropriate 'meson.build' files,
since the 'pyproject.toml' configuration only provides a way of running
``meson setup`` and ``meson compile`` before creating the binary distribution.

.. attention::

  The ``meson install`` (or ``cmake install``) must be done in a way that can be
  copied into the distribution and then installed to another location, instead of
  actually being installed to the system.
  This means that the compiled code **must be relocateable**, avoiding the use of
  absolute paths in configurations and dynamic linking.

The ``src_dir`` and ``prefix`` paths are always relative to the project
root directory, and default to ``src_dir = '.'`` and ``prefix = './build'``.
Currently these must all be a sub-directory relative to the 'pyproject.toml'
(e.g. a specified temporary directory).

The result should be equivalent to running the following commands:

.. code-block:: bash

  meson setup [setup_args] --prefix prefix [-Doption=val] build_dir src_dir
  meson compile [compile_args] -C build_dir
  meson install [install_args] -C build_dir

executed in the project directory, followed by copying all files in 'build/lib'
into the binary distribution's 'platlib' install path.

.. attention::

  The ``ignore`` patterns should be considered when including compiled
  extensions, for example to ensure that the extension shared object '.so' are
  *not ignored* and actually copied into the binary distribution.

Binary distribution install paths
---------------------------------

If there are some binary distribution files that need to be installed to a
location according to a local installation scheme
these can be specified within sub-tables.
Available install scheme keys, and **example** corresponding install locations, are:

* ``purelib`` ("pure" library Python path): ``{prefix}/lib/python{X}.{Y}/site-packages/``
* ``platlib`` (platform specific Python path): ``{prefix}/lib{platform}/python{X}.{Y}/site-packages/``

  .. note::

    Both ``purelib`` and ``platlib`` install to the base 'site-packages'
    directory, so any files copied to these paths should be placed within a
    desired top-level package directory.

* ``headers`` (INCLUDE search paths): ``{prefix}/include/{site}/python{X}.{Y}{abiflags}/{distname}/``
* ``scripts`` (executable search path): ``{prefix}/bin/``

  .. attention::

    Even though any files added to the ``scripts`` path will be installed to
    the ``bin`` directory, there is often an issue with the 'execute' permission
    being set correctly by the installer (e.g. ``pip``).
    The only verified way of ensuring an executable in the 'bin' directory is to
    use the ``[project.scripts]`` section to add an entry point that will then
    run the desired executable as a sub-process.

* ``data`` (generic data path): ``{prefix}/``

.. code-block:: toml

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


Config Settings
---------------

As described in :pep:`517`, an installer front-end may implement support for
passing additional options to the backend
(e.g. ``--config-settings`` in ``pip``).
These options may be defined in the ``tool.pyproj.config`` table, which is used
to validate the allowed options, fill in default values, and cast to
desired types.
These settings, updated by any values passed from the front-end installer,
are available in any processing hook.
Combined with an entry-point ``kwargs``, these can be used to keep all
conditional dependencies listed in ``pyproject.toml``.

.. note::

  The type is derived from the value parsed from ``pyproject.toml``.
  For example, the value of ``3`` is parsed as an integer, while ``3.0`` is parsed
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

.. code-block:: toml

  [tool.pyproj.config]
  a_cfg_option = false
  another_option = ["foo", "bar"]

  [tool.pyproj.prep]
  entry = "pkgaux:prep"
  kwargs = { deps = ["additional_build_dep >= 1.2.3"] }

.. code-block:: python
  :caption: ``pkgaux/__init__.py``

  def prep( builder, logger, deps ):

    if builder.config.a_cfg_option:
      builder.build_requires |= set(deps)

    if builder.config.another_option == 'foo':
      ...

    elif builder.config.another_option == 'bar':
      ...

In this example, the command
``pip install --config-settings a_cfg_option=true ...`` will cause the
'additional_build_dep' to be installed before the build occurs.
The value of ``another_option`` may be either ``foo`` or ``bar``,
and all other values will raise an exception before reaching the entry-point.

