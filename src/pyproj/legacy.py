import os
import os.path as osp
import sys
import shutil
import logging
import tempfile

from .build_dummy import (
  build_sdist_dummy )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def legacy_setup_content( pyproj, sdist ):
  """

  Notes
  -----
  Assumes that `pyproj.dist_source_prep` has already been run, and all files have
  already been added to `sdist`
  """

  # NOTE: the build requirements are added to the installation requirements,
  # since legacy installation does not truly support the 'setup_requires' method
  # provided by setuptools

  # NOTE: 'wheel' is added as a build dependency because pip will not even try
  # to run 'bdist_wheel' if 'wheel' isn't already installed

  build_requires = pyproj.build_requires | set(['wheel', ])

  pkg_info = pyproj.pkg_info.add_dependencies(
    deps = build_requires )

  requires = '\n'.join([
    str(d) for d in  pkg_info.requires_dist ]).encode('utf-8')

  sources = '\n'.join( [
    file
    for file, hash, size in sdist.records ] ).encode('utf-8')

  top_level = '\n'.join( pyproj.top_level ).encode('utf-8')

  with open( osp.join( osp.dirname(__file__), '_legacy_setup.py' ), 'r' ) as fp:
    legacy_setup_py = fp.read()

  build_requires = [ str(r) for r in build_requires ]
  print(build_requires)

  legacy_setup_py = legacy_setup_py.format(
    egg_info_name = f"'{pyproj.pkg_info.name_normed}.egg-info'",
    pkg_info = pkg_info.encode_pkg_info(),
    requires = requires,
    build_requires = str(build_requires),
    sources = sources,
    top_level = top_level,
    entry_points = pkg_info.encode_entry_points(),
    build_backend = f"'{pyproj.build_backend}'",
    backend_path = pyproj.backend_path )

  print(legacy_setup_py)

  sdist.write(
    dst = f'{sdist.base_path}/setup.py',
    data = legacy_setup_py )
