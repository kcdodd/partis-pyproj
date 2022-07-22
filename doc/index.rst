
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
generating files, or running another build program (E.G. https://mesonbuild.com/).
The 'copy' operation is specified by a sequence of find-filter-copy pattern based
rules. Instead of using a ``MANIFEST.in`` file or ``find_packages`` routine,
this gives full control within the ``pyproject.toml`` file over what goes into
the distribution and where it ends up.

Copy Operations
---------------

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


* Each item listed in ``copy`` for a distribution is treated like the
  keyword arguments of
  :func:`shutil.copyfile`
  or
  :func:`shutil.copytree`,
  depending on whether the ``src`` is a file or a directory.
* The ``dst`` is relative to a distribution archive base directory.
* If the item is a single string, it is expanded as ``dst = src``.
* A ``glob`` pattern may be used to match files or directories,
  supporting the ``**`` recursive operator, which is expanded to zero or more
  matches relative to ``src``.
  When ``glob`` is used, the destination path is relative to ``dst``, taken from the
  source path relative to ``src``.
* The ``ignore`` list is treated like the arguments to
  :func:`shutil.ignore_patterns`,
  before it is passed to the :func:`shutil.copytree` function.
* Every *file* explicitly listed as a ``src`` will be copied, even if it
  matches one of the ``ignore`` patterns.
* The ``ignore`` patterns may be specified for all distributions in
  ``tool.pyproj.dist``, specifically for ``tool.pyproj.dist.binary`` or
  ``tool.pyproj.dist.source``, or individually for each copy operation
  ``{ src = '...', dst = '...', ignore = [...] }``.
  The ignore patterns are inherited at each level of specificity.
* If an ignore pattern **does not** contain any path separators, it is matched to
  the **base-name** of every file or directory being considered.
* If an ignore pattern **contains** a path separator, then it is matched to the
  **full path** relative to either:

  * The root project directory for ``tool.pyproj.dist.ignore``,
    ``tool.pyproj.dist.binary.ignore``, and ``tool.pyproj.dist.source.ignore``.
  * ``src`` for any ``copy.ignore`` specified within a ``copy`` operation.

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

* ``tool.pyproj.prep`` : called to fill in 'dynamic' metadata, or update
  the 'build_requires' list of requirements needed to build a binary distribution.
* ``tool.pyproj.dist.prep`` : called first for both source or binary distributions.
* ``tool.pyproj.dist.source.prep``: called before copying files to a source distribution.
* ``tool.pyproj.dist.binary.prep``: called before copying files to a binary distribution.

  .. note::

    If the Meson Build commands are specified, those will be run
    **before** ``tool.pyproj.dist.binary.prep``, but
    **after** ``tool.pyproj.dist.prep``.

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


Meson Build system
------------------

With the optional dependency ``partis-pyproj[meson]``, support is included for
the Meson Build system https://mesonbuild.com/ as a method to compile extensions
and non-Python code.
To use this feature, the source directory must contain appropriate 'meson.build' files,
since the 'pyproject.toml' configuration only provides a way of running
``meson setup`` and ``meson compile`` before creating the binary distribution.
Also, the ``meson install`` must be able to be done in a way that can be
copied into the distribution, instead of actually being installed to the system.

The ``src_dir`` and ``prefix`` paths are always relative to the project
root directory, and default to ``src_dir = '.'`` and ``prefix = './build'``.
If ``build_dir`` is given, it is also relative to the project root directory,
otherwise the build will occur in a temporary directory that is removed after
"installing" to ``prefix``.

The result should be equivalent to running the following commands:

.. code-block:: bash

  meson setup [setup_args] --prefix prefix [-Doption=val] build_dir src_dir
  meson compile [compile_args] -C build_dir
  meson install [install_args] -C build_dir

For example, the following configuration,

.. code-block:: toml

  [tool.pyproj.meson]
  # flag that the meson commands should be run.
  compile = true

  # automatically use available number of parallel build jobs
  compile_args = [
    '-j', '-1' ]

  # location of root 'meson.build' and 'meson_options.txt' files
  src_dir = '.'
  # location to create temporary build files (optional)
  build_dir = 'build'
  # location to place final build targets
  prefix = 'build'

  [tool.pyproj.meson.options]
  # Custom build options
  custom_feature=enabled

  [tool.pyproj.dist.binary.platlib]
  # binary distribution platform specific install path
  copy = [
    { src = 'build/lib', dst = 'my_project' } ]

will result in the commands executed in the project directory,
followed by copying all files in 'build/lib' into the binary distribution's
'platlib' install path:

.. code-block:: bash

  meson setup --prefix ./build -Dcustom_feature=enabled ./build .
  meson compile -j -1 -C ./build
  meson install -C ./build

.. attention::

  The ``ignore`` patterns should be considered specially when including compiled
  extensions, for example to ensure that the extension shared object '.so' are
  actually copied into the binary distribution.


Support for 'legacy setup.py'
-----------------------------

There is an optional mechanism to add support of setup.py for non PEP 517
compliant installers that must install a package from source.
This option does **not** use setuptools in any way, since that wouldn't allow
the faithful interpretation of the build process defined in 'pyproject.toml',
nor of included custom build hooks.

.. attention::

  Legacy support is likely fragile and **not guaranteed** to be successful.
  It would be better to recommend the end-user simply update their package manager
  to be PEP-517 capable, such as ``pip >= 18.1``, or to provide pre-built wheels
  for those users.

If enabled, a 'setup.py' file is generated when building a source
distribution that, if run by an installation front-end, will attempt to emulate
the setuptools CLI 'egg_info', 'bdist_wheel', and 'install' commands:

* The 'egg_info' command copies out a set of equivalent '.egg-info'
  files, which should subsequently be ignored after the meta-data is extracted.

* The 'bdist_wheel' command will attempt to simply call the backend code as
  though it were a PEP-517 build, assuming the build dependencies were
  satisfied by the front-end (added to the regular install
  dependencies in the '.egg-info').

* If 'install' is called ( instead of 'bdist_wheel' ), then it will
  again try to build the wheel using the backend, and then try to use pip
  to handle installation of the wheel as another sub-process.
  This will fail if pip is not the front-end.

This 'legacy' feature is enabled by setting the value of
``tool.pyproj.dist.source.add_legacy_setup``.

.. code-block:: toml

  [tool.pyproj.dist.source]

  # adds support for legacy 'setup.py'
  add_legacy_setup = true


.. toctree::
  :maxdepth: 2
  :hidden:

  glossary
  src/index
