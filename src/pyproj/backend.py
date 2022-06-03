import os
import os.path as osp
import sys
import shutil
import logging
import tempfile
import re

from collections.abc import (
  Mapping,
  Sequence )

from . import (
  valid_keys,
  mapget,
  dist_build,
  PkgInfoReq,
  PyProjBase,
  dist_binary_wheel,
  dist_source_targz )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class UnsupportedOperation( Exception ):
  """
  Note
  ----
  If the backend cannot produce an dist because a dependency is missing,
  or for another well understood reason, it should raise an exception of a
  specific type which it makes available as UnsupportedOperation on the
  backend object.

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0517/
  """
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def backend_init(
  root = '.',
  config_settings = None,
  logger = None ):
  """Called to inialialize the backend upon a call to one of the hooks

  Parameters
  ----------
  root : str
    Directory containing 'pyproject.toml'
  logger : :class:`logging.Logger`
    Logger to use

  Returns
  -------
  PyProjBase
  """

  logger = logger or logging.getLogger( __name__ )

  pyproj = PyProjBase(
    root = root,
    config_settings = config_settings,
    logger = logger )

  # NOTE: this is mainly used for debugging, since front-ends don't seem to have
  # an option to set logging level for the backend.
  # logging.basicConfig(
  #   level = logging.NOTSET,
  #   format = "{name}:{levelname}: {message}",
  #   style = "{" )

  return pyproj


#-----------------------------------------------------------------------------
def get_requires_for_build_sdist(
  config_settings = None ):
  """
  Note
  ----
  This hook MUST return an additional list of strings containing PEP 508
  dependency specifications, above and beyond those specified in the
  pyproject.toml file. These dependencies will be installed when calling the
  build_sdist hook.

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0517/#get-requires-for-build-sdist
  """

  return list()

#-----------------------------------------------------------------------------
def build_sdist(
  dist_directory,
  config_settings = None ):
  """
  Note
  ----
  Must build a .tar.gz source distribution and place it in the specified
  dist_directory. It must return the basename (not the full path) of the
  .tar.gz file it creates, as a unicode string.

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0517/#build-sdist
  """

  pyproj = backend_init(config_settings = config_settings)

  pyproj.dist_prep()

  pyproj.dist_source_prep()

  with dist_source_targz(
    pkg_info = pyproj.pkg_info,
    outdir = dist_directory,
    logger = pyproj.logger ) as dist:

    pyproj.dist_source_copy(
      dist = dist )

  return dist.outname

#-----------------------------------------------------------------------------
def get_requires_for_build_wheel(
  config_settings = None ):
  """
  Note
  ----
  This hook MUST return an additional list of strings containing
  PEP 508 dependency specifications, above and beyond those specified in the
  pyproject.toml file, to be installed when calling the build_wheel or
  prepare_metadata_for_build_wheel hooks.

  Note
  ----
  pip appears to not process environment markers for deps returned
  by get_requires_for_build_*, and may falsly report
  ``ERROR: Some build dependencies...conflict with the backend dependencies...``

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0517/#get-requires-for-build-wheel
  """

  pyproj = backend_init(config_settings = config_settings)

  # filter out any dependencies already listed in the 'build-system'.
  # NOTE: pip appears to not process environment markers for deps returned
  # by get_requires_for_build_*, and may falsly report
  # > ERROR: Some build dependencies...conflict with the backend dependencies...
  build_requires = pyproj.build_requires - set([
    PkgInfoReq(r)
    for r in mapget( pyproj.pptoml, 'build-system.requires', list() ) ])

  reqs = [ str(r) for r in build_requires ]

  pyproj.logger.info(f'get_requires_for_build_wheel: {reqs}')

  return reqs

#-----------------------------------------------------------------------------
def prepare_metadata_for_build_wheel(
  metadata_directory,
  config_settings = None ):
  """
  Note
  ----
  Must create a .dist-info directory containing wheel metadata inside the
  specified metadata_directory (i.e., creates a directory like
  {metadata_directory}/{package}-{version}.dist-info/).

  See Also
  --------
  * https://www.python.org/dev/peps/pep-0517/#prepare-metadata-for-build-wheel
  """

  pyproj = backend_init(config_settings = config_settings)

  # TODO: abstract 'wheel metadata' from needing to actually make a dummy wheel file
  with dist_binary_wheel(
    pkg_info = pyproj.pkg_info,
    outdir = metadata_directory,
    logger = pyproj.logger ) as dist:

    pass


  import zipfile
  with zipfile.ZipFile( dist.outpath ) as fp:
    fp.extractall(metadata_directory)

  return dist.dist_info_path

#-----------------------------------------------------------------------------
def build_wheel(
  wheel_directory,
  config_settings = None,
  metadata_directory = None ):
  """
  Note
  ----
  Must build a .whl file, and place it in the specified wheel_directory.
  It must return the basename (not the full path) of the .whl file it creates,
  as a unicode string.


  See Also
  --------
  * https://www.python.org/dev/peps/pep-0517/#build-wheel
  """

  pyproj = backend_init(config_settings = config_settings)

  pyproj.dist_prep()

  pyproj.dist_binary_prep()

  with dist_binary_wheel(
    pkg_info = pyproj.pkg_info,
    build = dist_build(
      pyproj.binary.get('build_number', None),
      pyproj.binary.get('build_suffix', None) ),
    compat = pyproj.binary.compat_tags,
    outdir = wheel_directory,
    logger = pyproj.logger ) as dist:

    pyproj.dist_binary_copy(
      dist = dist )

  pyproj.logger.info(
    f"Top level packages {dist.top_level}")

  return dist.outname

#-----------------------------------------------------------------------------
# def prepare_metadata_for_build_editable(
#   metadata_directory,
#   config_settings = None ):
#   pass


#-----------------------------------------------------------------------------
# def build_editable(
#   wheel_directory,
#   config_settings = None,
#   metadata_directory = None ):
#   pass
