
Packaging (:mod:`partis.pyproj`)
================================

The :mod:`partis.pyproj <partis.pyproj>` package aims to be very simple and
transparent implementation of a :pep:`517` build back-end.
This package was developed to avoid dependence on the opaque lack of control
provided by :mod:`setuptools` in the distribution process,
and to address the limited selection of utilities available for seemingly
simple packaging tasks, such as creating a wheel file with desired contents.

* It does not attempt to inspect anything from the contents of the package
  being distributed / installed
* relies on an understanding that a distribution is simply a collection of files
  including package meta-data written in particular formats.
* The back-end implementation strives to be compliant with all relevant
  specifications.


.. toctree::
  :maxdepth: 2
  :hidden:

  userguide/index
  src/index
