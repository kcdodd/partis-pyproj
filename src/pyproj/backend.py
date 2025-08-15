from __future__ import annotations
import os
import os.path as osp
import sys
import json
from subprocess import check_output, check_call
import shutil
from copy import copy
import logging
from logging import (
  basicConfig,
  getLogger,
  Logger)
import tempfile
import re

from pathlib import (
  Path,
  PurePath,
  PurePosixPath)

from collections.abc import (
  Mapping,
  Sequence )

from . import (
  valid_keys,
  ValidationError,
  mapget,
  hash_sha256,
  dist_build,
  PkgInfoReq,
  PyProjBase,
  dist_source_targz,
  dist_binary_wheel,
  dist_binary_editable)

#===============================================================================
def backend_init(
  root: str|Path = '',
  config_settings: dict|None = None,
  logger: Logger|None = None,
  editable: bool = False,
  init_logging: bool = True):
  """Called to inialialize the backend upon a call to one of the hooks

  Parameters
  ----------
  root :
    Directory containing 'pyproject.toml'
  logger :
    Logger to use
  editable:
    True if creating an editable installation

  Returns
  -------
  PyProjBase
  """

  # NOTE: this is mainly used for debugging, since front-ends don't seem to have
  # an option to set logging level for the backend.
  root_logger = getLogger()

  if init_logging and not root_logger.handlers:
    basicConfig(
      level = os.environ.get('PARTIS_PYPROJ_LOGLEVEL', 'INFO').upper(),
      format = "{message}",
      style = "{" )

  root = Path(root)
  logger = logger or getLogger( __name__ )

  pyproj = PyProjBase(
    root = root,
    config_settings = config_settings,
    logger = logger,
    editable = editable)

  return pyproj


#-----------------------------------------------------------------------------
def get_requires_for_build_sdist(
  config_settings: dict|None = None ):
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
def get_requires_for_build_wheel(
  config_settings: dict|None = None,
  _editable: bool = False):
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
  print(f"get_requires_for_build_wheel({config_settings=})")

  pyproj = backend_init(
    config_settings = config_settings,
    editable = _editable)

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
def get_requires_for_build_editable(config_settings=None):
  print(f"get_requires_for_build_editable({config_settings=})")
  deps = get_requires_for_build_wheel(config_settings, _editable=True)

  # add so incremental virtualenv can be created
  deps += ['pip', 'virtualenv ~= 20.28.0']
  return deps

#-----------------------------------------------------------------------------
def build_sdist(
  dist_directory,
  config_settings: dict|None = None ):
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
def prepare_metadata_for_build_wheel(
  metadata_directory,
  config_settings: dict|None = None,
  _editable: bool = False):
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

  pyproj = backend_init(
    config_settings = config_settings,
    editable = _editable)

  # TODO: abstract 'wheel metadata' from needing to actually make a dummy wheel file
  with dist_binary_wheel(
    pkg_info = pyproj.pkg_info,
    outdir = metadata_directory,
    logger = pyproj.logger ) as dist:

    pass


  import zipfile
  with zipfile.ZipFile( dist.outpath ) as fp:
    fp.extractall(metadata_directory)

  # NOTE: dist_info_path is a POSIX path, need to convert to OS path first
  # PIP assums the return value is a string
  return os.fspath(Path(dist.dist_info_path))

#-----------------------------------------------------------------------------
def prepare_metadata_for_build_editable(
  metadata_directory,
  config_settings = None ):

  return prepare_metadata_for_build_wheel(
    metadata_directory,
    config_settings,
    _editable = True)

#-----------------------------------------------------------------------------
def build_wheel(
  wheel_directory,
  config_settings: dict|None = None,
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

  try:
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


    record_hash = dist.finalize(metadata_directory)
    pyproj.logger.info(
      f"Top level packages {dist.top_level}")

  except ValidationError as e:
    known_exception_type = copy(e)
    raise known_exception_type from e.__cause__

  return dist.outname

#-----------------------------------------------------------------------------
def build_editable(
  wheel_directory,
  config_settings = None,
  metadata_directory = None ):

  pyproj = backend_init(
    config_settings = config_settings,
    editable = True)

  # hash the path of root source directory
  # src_hash = hash_sha256(str(pyproj.root).encode('utf-8'))[0]
  # whl_root = Path(tempfile.gettempdir())/'partis_pyproj_editables'/src_hash
  # TODO: add option for desired editable virtual wheel location
  whl_root = pyproj.root/'build'/'.editable_wheel'
  venv_dir = pyproj.root/'build'/'.editable_venv'

  if whl_root.exists():
    # TODO: add status file to avoid accidentally deleting the wrong directory
    shutil.rmtree(whl_root)

  whl_root.mkdir(0o700, parents=True)

  venv_bin = venv_dir/'bin'
  venv_py = str(venv_bin/'python')

  # incremental = len(pyproj.targets) > 0
  incremental = False
  _PATH = os.environ['PATH']
  _sys_path = list(sys.path)

  if incremental:
    # NOTE: this should clone the current build environment packages to reproduce
    # during incremental builds
    # add virtualenv after, otherwise dist_binary will delete it
    requirements = check_output(['python', '-m', 'pip', 'freeze'])
    requirements_file = whl_root/'requirements.txt'
    requirements_file.write_bytes(requirements)

    check_call(['virtualenv', str(venv_dir)])
    check_call([venv_py, '-m', 'pip', 'install', '--force-reinstall', '-r', str(requirements_file)])

    os.environ['PATH'] = str(venv_bin) + os.pathsep + _PATH

    res = check_output([
      venv_py,
      '-c',
      "import sys; import json; sys.stdout.write(json.dumps(sys.path))"])

    sys_path = json.loads(res.decode('utf-8', errors = 'ignore'))
    # sys.path[:] = sys_path

  try:
    pyproj.dist_prep()

    pyproj.dist_binary_prep()

    with dist_binary_editable(
      root = pyproj.root,
      # enable incremental rebuilds if there are any targets
      incremental = incremental,
      pptoml_checksum = pyproj.pptoml_checksum,
      whl_root = whl_root,
      pkg_info = pyproj.pkg_info,
      build = dist_build(
        pyproj.binary.get('build_number', None),
        pyproj.binary.get('build_suffix', None) ),
      compat = pyproj.binary.compat_tags,
      outdir = wheel_directory,
      logger = pyproj.logger ) as dist:

      pyproj.dist_binary_copy(
        dist = dist )

      record_hash = dist.finalize(metadata_directory)

  finally:
    os.environ['PATH'] = _PATH
    sys.path[:] = _sys_path


  pyproj.logger.info(
    f"Top level packages {dist.top_level}")

  return dist.outname

#===============================================================================
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
