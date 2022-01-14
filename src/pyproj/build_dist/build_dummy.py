import os
import os.path as osp
import io
import warnings
import stat

import shutil

from ..norms import (
  norm_path,
  norm_data,
  norm_mode )

from ..pkginfo import PkgInfo

from .build_base import build_base

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_sdist_dummy( build_base ):

  #-----------------------------------------------------------------------------
  def __init__( self,
    pkg_info,
    outdir = None,
    tmpdir = None,
    logger = None ):

    if not isinstance( pkg_info, PkgInfo ):
      raise ValueError(f"pkg_info must be instance of PkgInfo: {pkg_info}")

    self.pkg_info = pkg_info

    sdist_name_parts = [
      self.pkg_info.name_normed,
      self.pkg_info.version ]

    self.base_path = '-'.join( sdist_name_parts )

    self.metadata_path = self.base_path + '/PKG-INFO'

    super().__init__(
      outname = '-'.join( sdist_name_parts ) + '.tar.gz',
      outdir = outdir,
      tmpdir = tmpdir,
      logger = logger )


  #-----------------------------------------------------------------------------
  def make_buildfile( self ):
    pass

  #-----------------------------------------------------------------------------
  def close_buildfile( self ):
    pass

  #-----------------------------------------------------------------------------
  def copy_buildfile( self ):
    pass

  #-----------------------------------------------------------------------------
  def remove_buildfile( self ):
    pass

  #-----------------------------------------------------------------------------
  def finalize( self ):
    pass
