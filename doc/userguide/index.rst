
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

.. code:: toml

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

  [tool.pyproj.dist.binary]
  # define what files/directories should be copied into a binary distribution
  # the 'dst' will correspond to the location of the file in 'site-packages'
  copy = [
    { src = 'src/my_project', dst = 'my_project' } ]

  # list the names of the top-level packages
  top_level = [ 'my_project' ]

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

Binary distribution install paths
---------------------------------

If there are some binary distribution files that need to be installed to a
location according to a local installation scheme (not the regular modules)
these can be specified within sub-tables.
Available install scheme keys, and example corresponding install locations, are:

* ``data`` : '{prefix}/'
* ``headers`` : '{prefix}/include/{site}/python{X}.{Y}{abiflags}/{distname}/'
* ``platlib`` : '{prefix}/lib/python{X}.{Y}{platform}/site-packages/'
* ``purelib`` : '{prefix}/lib/python{X}.{Y}/site-packages/'
* ``scripts`` : '{prefix}/bin/'

.. code:: toml

  [tool.pyproj.dist.binary.data]
  copy = [
    { src = 'build/data.dat', dst = 'data.dat' } ]

  [tool.pyproj.dist.binary.headers]
  copy = [
    { src = 'build/header.hpp', dst = 'header.hpp' } ]

  [tool.pyproj.dist.binary.platlib]
  copy = [
    { src = 'build/pltlib.a', dst = 'pltlib.a'} ]

  [tool.pyproj.dist.binary.purelib]
  copy = [
    { src = 'build/purlib.py', dst = 'purlib.py'} ]

  [tool.pyproj.dist.binary.scripts]
  copy = [
    { src = 'build/script.py', dst = 'script.py'} ]

Adding a custom pre-processing hook
-----------------------------------

The backend provides a mechanism to perform an arbitrary operation before any
files are copied into the distribution.
The ``prep`` hook currently must be a pure module, a directory with a
``__init__.py`` file, at the same level as the `pyproject.toml` specified
similar to a package ``entry_point``.
Keyword arguments may also be defined and will be passed to the function.

.. code:: py

  [tool.pyproj.dist.binary.prep]
  # hook defined in a python module
  entry = "a_custom_prep_module:a_prep_function"

  [tool.pyproj.dist.binary.prep.kwargs]
  # define keyword argument values to be passed to the pre-processing hook
  a_custom_argument = 'some value'


This will be treated by the back-end in a way that should be equivalent to the
following code run in the `pyproject.toml` directory:

.. code:: python

  import a_custom_prep_module

  a_custom_prep_module.a_prep_function(
    build_system,
    a_custom_argument = 'some value' )


The ``build_system`` argument is the instance of
:class:`PyProjBase <partis.pyproj.pyproj.PyProjBase>` calling the function
during processing of :meth:`PyProjBase.dist_binary_prep`.

.. note::

  Only those requirements listed in ``build-system.requires``
  will be importable by the specified code.

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

.. code:: toml

  [tool.pyproj.dist.source]

  # adds support for legacy 'setup.py'
  add_legacy_setup = true
