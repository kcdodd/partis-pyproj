import os
import os.path as osp
import io
import warnings
import stat

import shutil

from .norms import (
  norm_path,
  norm_data,
  norm_mode )

from .pkginfo import PkgInfo

from .build_targz import build_targz

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class build_sdist_targz( build_targz ):
  """
  Parameters
  ----------
  pkg_info : PkgInfo
  outdir : str
    Path to directory where the wheel file should be copied after completing build.
  tmpdir : None | str
    If not None, uses the given directory to place the temporary wheel file before
    copying to final location.
    My be the same as outdir.

  See Also
  --------

  """
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
  def finalize( self ):
    """Commit and write the metadata to the sdist

    """

    self.write(
      dst = self.metadata_path,
      data = self.pkg_info.encode_pkg_info() )
