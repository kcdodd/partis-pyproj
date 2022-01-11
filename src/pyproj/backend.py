import os
import os.path as osp
import sys
import shutil
import logging
import tempfile

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

class BuildBackendError( Exception ):
  pass


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class BuildBackend:
  """Custom in-tree source build backend hook

  https://www.python.org/dev/peps/pep-0517

  Implementation directly calls the backend provided by setuptools
  https://github.com/pypa/setuptools/blob/main/setuptools/build_meta.py
  """

  UnsupportedOperation = BuildBackendError

  #-----------------------------------------------------------------------------
  def __init__( self ):

    logging.basicConfig(
      level = logging.NOTSET,
      format = "{name}:{levelname}: {message}",
      style = "{" )

    self.logger = logging.getLogger( type(self).__name__ )

    self.pyproj = PyProjBase(
      root = '.',
      logger = self.logger )

  #-----------------------------------------------------------------------------
  def get_requires_for_build_sdist(self, config_settings=None):

    return list()

  #-----------------------------------------------------------------------------
  def build_sdist(self, sdist_directory, config_settings=None):

    self.pyproj.dist_source_prep()

    with build_sdist_targz(
      pkg_info = self.pyproj.pkg_info,
      outdir = sdist_directory,
      logger = self.logger ) as sdist:

      self.pyproj.dist_source_copy(
        sdist = sdist )

    return sdist.outname

  #-----------------------------------------------------------------------------
  def get_requires_for_build_wheel( self,
    config_settings = None):


    return list()

  #-----------------------------------------------------------------------------
  # def prepare_metadata_for_build_wheel(self,
  #   metadata_directory,
  #   config_settings = None ):
  #
  #   pass

  #-----------------------------------------------------------------------------
  def build_wheel(self,
    wheel_directory,
    config_settings = None,
    metadata_directory = None ):

    self.pyproj.dist_binary_prep()

    with build_bdist_wheel(
      pkg_info = self.pyproj.pkg_info,
      outdir = wheel_directory,
      top_level = self.pyproj.top_level,
      logger = self.logger ) as bdist:

      self.pyproj.dist_binary_copy(
        bdist = bdist )

    return bdist.outname

  #-----------------------------------------------------------------------------
  # def prepare_metadata_for_build_editable(self,
  #   metadata_directory,
  #   config_settings = None ):
  #
  #
  #   return prepare_metadata_for_build_editable(
  #     metadata_directory = metadata_directory,
  #     config_settings = config_settings )

  #-----------------------------------------------------------------------------
  # def build_editable(
  #   wheel_directory,
  #   config_settings = None,
  #   metadata_directory = None ):
  #
  #   return build_editable(
  #     wheel_directory = wheel_directory,
  #     config_settings = config_settings,
  #     metadata_directory = metadata_directory )


#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

_BACKEND = BuildBackend( )

get_requires_for_build_wheel = _BACKEND.get_requires_for_build_wheel
get_requires_for_build_sdist = _BACKEND.get_requires_for_build_sdist
# prepare_metadata_for_build_wheel = _BACKEND.prepare_metadata_for_build_wheel
build_wheel = _BACKEND.build_wheel
build_sdist = _BACKEND.build_sdist
