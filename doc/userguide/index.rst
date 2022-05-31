
User Guide
==========

The :mod:`partis.pyproj <partis.pyproj>` package aims to be very simple and
transparent PEP-517 :cite:`pep0517` build back-end.
This package was developed to avoid dependence on the opaque lack of control
provided by :mod:`setuptools` in the distribution process,
and to address the limited selection of utilities available for seemingly
simple packaging tasks, such as creating a wheel file.
It does not attempt to inspect anything from the contents of the package
being distributed / installed, and instead relies on an understanding that a
distribution is simply a collection of files including package meta-data written
in particular formats.
The back-end implementation strives to be compliant with all relevant
specifications.

While the standards describe the form of package meta-data, they do not describe
what information is needed to turn the files in a repository into a
distribution.
The approach to those needed but unspecified configuration options is to make
them behave like the file manipulation routines available in the Python
standard library
:mod:`shutil`,
but where the ``dst`` of the
operation is actually into a distribution file ( ``*.tar.gz`` or ``*.whl`` ).

Use with 'pyproject.toml' files
-------------------------------

.. code-block:: toml

  # pyproject.toml

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
  # define glob patterns of files to ignore for any type of distribution
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


* Each item listed in ``copy`` for a distribution are treated like the
  keyword arguments of
  :func:`shutil.copyfile`
  or
  :func:`shutil.copytree`,
  depending on whether the ``src`` is a file or a directory.
* The ``dst`` is relative to the relevant distribution archive root directory.
* If the item is a single string, it is expanded as ``dst = src``.
* The ``ignore`` list is treated like the arguments to
  :func:`shutil.ignore_patterns`,
  which is then passed to the :func:`shutil.copytree` function.
* Every *file* explicitly listed as a ``src`` will be copied, even if it
  matches one of the ``ignore`` patterns.
* The ``ignore`` patterns may be specified for all distributions in
  ``tool.pyproj.dist``, specifically for ``tool.pyproj.dist.binary`` or
  ``tool.pyproj.dist.source``, or individually for each copytree operation
  ``{ src = '...', dst = '...', ignore = [...] }``.
  The ignore patterns are accumulated at each level of specificity.

Optionally, a ``glob`` pattern may also be used to match files or directories,
with is expanded to zero or more matches.
However, when ``glob`` is used, the purpose of ``src`` and ``dst`` is strictly
to specify relative paths.
All accumulated ``ignore`` patterns, however, remain relative to the root project
directory.
For example, the following will recursively copy all files ending int ``.py``,
except for files named ``bad_file.py``.

.. code-block:: toml

  [[tool.pyproj.dist.binary.purelib.copy]]
  src = 'src/my_project'
  glob = '**/*.py'
  dst = 'my_project'
  ignore = '**/bad_file.py'

Binary distribution install paths
---------------------------------

If there are some binary distribution files that need to be installed to a
location according to a local installation scheme
these can be specified within sub-tables.
Available install scheme keys, and **example** corresponding install locations, are:

* ``purelib`` (generic Python path): '{prefix}/lib/python{X}.{Y}/site-packages/'
* ``platlib`` (platform specific Python path): '{prefix}/lib{platform}/python{X}.{Y}/site-packages/'

  .. note::

    Both ``purelib`` and ``platlib`` install to the base 'site-packages'
    directory, so any files copied to these paths should be placed within a
    desired top-level package directory.

* ``headers`` (INCLUDE search paths): '{prefix}/include/{site}/python{X}.{Y}{abiflags}/{distname}/'
* ``scripts`` (executable search path): '{prefix}/bin/'

  .. attention::

    Even though any files added to the ``scripts`` path will be installed to
    the ``bin`` directory, there is often an issue with the 'execute' permission
    being set correctly by the installer (e.g. ``pip``).
    The only verified way of ensuring an executable in the 'bin' directory is to
    use the ``[project.scripts]`` section to add an entry point that will then
    run the desired executable as a sub-process.

* ``data`` (generic data): '{prefix}/'

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

Processing hooks
----------------

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

    The return value of the ``tool.pyproj.dist.binary.prep`` hook is also used to
    customize the compatibility tags for the binary distribution
    (according to https://peps.python.org/pep-0425/) as a list of tuples
    ``( py_tag, abi_tag, plat_tag )``.

    If no tags are returned from the hook, the default tags will be set to
    ``( 'py{X}', 'none', 'any' )``, or if any files are copied to the
    ``platlib`` install path the compatibility will be used for the current Python
    interpreter.

The hook must be a pure python module (a directory with an
``__init__.py`` file), relative to the 'pyproject.toml'.
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


This will be treated by the back-end equivalent to the
following code run from the `pyproject.toml` directory:

.. code:: python

  import a_custom_prep_module

  a_custom_prep_module.a_prep_function(
    build_system,
    logger,
    a_custom_argument = 'some value' )


The ``build_system`` argument is an instance of
:class:`PyProjBase <partis.pyproj.pyproj.PyProjBase>`, and ``logger``
is an instance of :class:`logging.Logger`.

.. attention::

  Only those requirements listed in ``build-system.requires``
  will be importable by the specified code.

Dynamic Metadata
----------------

As described in PEP 621, field values in the 'project' table may be deferred
to the backend by listing the keys in 'dynamic'.
If 'dynamic' is a non-empty list, the 'tool.pyproj.prep' processing hook must
be used to fill in the missing values.

.. code-block:: toml

  [project]
  dynamic = ["version"]
  name = "my_pkg"

  ...

  [tool.pyproj.prep]
  entry = "aux:prep"

The hook should return a dictionary that contains the keys of the 'project'
table to update.

.. code-block:: python
  :caption: aux/__init__.py

  def prep( build_system, logger ):
    return dict(
      version = "1.2.3" )

Config Settings
---------------

As described in PEP 517, an installer front-end may implement support for
passing additional options to the backend
(e.g. '--config-settings' in 'pip' and 'build').
These options may be defined in the 'tool.pyproj.config' table, which is used
to validate the allowed options, fill in default values, and cast to
desired types.
These settings, updated by any values passed from the front-end installer,
are available in any processing hook.
The 'kwargs' option can also be used to keep all dependencies listed in
'pyproject.toml'.

.. note::

  The type is derived from the value parsed from 'pyproject.toml'.
  For example, the value of '3' is parsed as an integer, while '3.0' is parsed
  as a float.

  Boolean values passed to '--config-settings' are parsed by comparing to
  string values ``['true', 'True', 'yes', 'y', 'enable', 'enabled']``
  or ``['false', 'False', 'no', 'n', 'disable', 'disabled']``.

.. code-block:: toml

  [tool.pyproj.prep]
  entry = "aux:prep"
  kwargs = { deps = ["additional_build_dep >= 1.2.3"] }

  [tool.pyproj.config]
  a_cfg_option = false

.. code-block:: python
  :caption: aux/__init__.py

  def prep( build_system, logger, deps ):

    if build_system.config['a_cfg_option']:
      self.build_requires |= set(deps)

In this example, the command
``pip install --config-settings a_cfg_option=true ...`` will cause the
'additional_build_dep' to be installed before the build occurs.

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
