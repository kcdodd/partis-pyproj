Partis-PyProj
=============

The :mod:`partis.pyproj <partis.pyproj>` package aims to be very simple and
transparent PEP-517 :cite:`pep0517` build back-end.
This package was developed to avoid dependence on the opaque lack of control
`setuptools <https://setuptools.pypa.io>`_ provides to the distribution process,
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
`shutil <https://docs.python.org/3/library/shutil.html>`_,
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

  [tool.partis.pyproj.dist.any]
  # define glob patterns of files to ignore for any type of distribution
  ignore = [
    '__pycache__',
    '*.py[cod]',
    '*.so',
    '*.egg-info' ]

  [tool.partis.pyproj.dist.source]
  # define what files/directories should be copied into a source distribution
  copy = [
    'src',
    'pyproject.toml' ]

  [tool.partis.pyproj.dist.binary]
  # define what files/directories should be copied into a binary distribution
  # the 'dst' will correspond to the location of the file in 'site-packages'
  copy = [
    { src = 'src/my_project', dst = 'my_project' } ]

  # list the names of the top-level packages
  top_level = [ 'partis' ]

Each item assigned to the ``copy`` array for a distribution are treated like the
keyword arguments of
`shutil.copyfile <https://docs.python.org/3/library/shutil.html#shutil.copyfile>`_
or
`shutil.copytree <https://docs.python.org/3/library/shutil.html#shutil.copytree>`_,
depending on whether the the ``src`` is a file or a directory.
If the ``copy`` specifies a single string, it treats it like ``dst = src``.
The ``ignore`` list is treated like the result of
`shutil.ignore_patterns(*ignore) <https://docs.python.org/3/library/shutil.html#shutil.ignore_patterns>`_
is passed to the ``copytree`` function.
The ``ignore`` patterns may also be defined for only ``dist.binary`` or
``dist.source`` by listing them in the corresponding table instead of ``dist.any``.

Adding a custom pre-processing hook
-----------------------------------

The backend provides a mechanism to perform an arbitrary operation before any
files are copied into the distribution.
The ``prep`` hook currently must be a pure module, a directory with a
``__init__.py`` file, at the same level as the `pyproject.toml` specified
similar to a package ``entry_point``.
Keyword arguments may also be defined and will be passed to the function.

.. code:: py

  [tool.partis.pyproj.dist.binary.prep]
  # hook defined in a python module
  entry = "a_custom_prep_module:a_prep_function"

  [tool.partis.pyproj.dist.binary.prep.kwargs]
  # define keyword argument values to be passed to the pre-processing hook
  a_custom_argument = 'some value'


This will be treated by the back-end in a way that should be equivalent to the
following code run in the `pyproject.toml` directory:

.. code:: python

  import a_custom_prep_module

  a_custom_prep_module.a_prep_function(
    a_custom_argument = 'some value' )

Keep in mind that **only** those requirements listed in ``build-system.requires``
will be importable by the specified code.
