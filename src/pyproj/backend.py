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
  PyProjBase,
  build_bdist_wheel,
  build_sdist_targz )

from .norms import (
  allowed_keys,
  mapget )

try:
  import coverage
  coverage.process_startup()
except ImportError:
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class UnsupportedOperation( Exception ):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def backend_init( root = '.' ):
  """Called to inialialize the backend upon a call to one of the hooks
  """

  logger = logging.getLogger( __name__ )

  pyproj = PyProjBase(
    root = root,
    logger = logger )

  logging.basicConfig(
    level = logging.NOTSET,
    format = "{name}:{levelname}: {message}",
    style = "{" )

  return pyproj


#-----------------------------------------------------------------------------
def get_requires_for_build_sdist(
  config_settings = None ):
  """https://www.python.org/dev/peps/pep-0517/#get-requires-for-build-sdist
  """

  return list()

#-----------------------------------------------------------------------------
def build_sdist(
  sdist_directory,
  config_settings = None ):
  """https://www.python.org/dev/peps/pep-0517/#build-sdist
  """

  pyproj = backend_init()

  pyproj.dist_source_prep()

  with build_sdist_targz(
    pkg_info = pyproj.pkg_info,
    outdir = sdist_directory,
    logger = pyproj.logger ) as sdist:

    pyproj.dist_source_copy(
      sdist = sdist )

  return sdist.outname

#-----------------------------------------------------------------------------
def get_requires_for_build_wheel(
  config_settings = None ):
  """https://www.python.org/dev/peps/pep-0517/#get-requires-for-build-wheel
  """

  pyproj = backend_init()

  reqs = [ str(r) for r in pyproj.build_requires ]

  pyproj.logger.info(f'get_requires_for_build_wheel: {reqs}')

  return reqs

#-----------------------------------------------------------------------------
def prepare_metadata_for_build_wheel(
  metadata_directory,
  config_settings = None ):
  """https://www.python.org/dev/peps/pep-0517/#prepare-metadata-for-build-wheel
  """

  pyproj = backend_init()

  # TODO: abstract 'wheel metadata' from needing to actually make a dummy wheel file
  with build_bdist_wheel(
    pkg_info = pyproj.pkg_info,
    outdir = metadata_directory,
    top_level = pyproj.top_level,
    logger = pyproj.logger ) as bdist:

    pass


  import zipfile
  with zipfile.ZipFile( bdist.outpath ) as fp:
    fp.extractall(metadata_directory)

  return bdist.dist_info_path

#-----------------------------------------------------------------------------
def build_wheel(
  wheel_directory,
  config_settings = None,
  metadata_directory = None ):
  """https://www.python.org/dev/peps/pep-0517/#build-wheel
  """

  pyproj = backend_init()

  pyproj.dist_binary_prep()

  with build_bdist_wheel(
    pkg_info = pyproj.pkg_info,
    outdir = wheel_directory,
    top_level = pyproj.top_level,
    logger = pyproj.logger ) as bdist:

    pyproj.dist_binary_copy(
      bdist = bdist )

  return bdist.outname

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
