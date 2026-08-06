from __future__ import annotations
import os
import os.path as osp
import sys
import json
from functools import wraps
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
  norm_dist_name,
  norm_dist_filename,
  dist_build,
  PkgInfoReq,
  PyProjBase,
  dist_source_targz,
  dist_binary_wheel,
  dist_binary_editable)

#===============================================================================
def _reraise_known_errors(func):
  @wraps(func)
  def _wrapped(*args, **kwargs):
    try:
      return func(*args, **kwargs)
    except ValidationError as e:
      # This re-raises the exception from here, removing the intermediate frames
      known_exception_type = copy(e)
      raise known_exception_type from e.__cause__

  return _wrapped

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
@_reraise_known_errors
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
@_reraise_known_errors
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

  pyproj.logger.debug(f'get_requires_for_build_wheel: {reqs}')

  return reqs

#-----------------------------------------------------------------------------
@_reraise_known_errors
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
@_reraise_known_errors
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

  # cleanup dummy wheel file (not part of contract)
  dist.outpath.unlink()

  # NOTE: dist_info_path is a POSIX path, need to convert to OS path first
  # PIP assums the return value is a string
  return os.fspath(Path(dist.dist_info_path))

#-----------------------------------------------------------------------------
@_reraise_known_errors
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
  pyproj.logger.debug(
    f"Top level packages {dist.top_level}")

  return dist.outname

#-----------------------------------------------------------------------------
@_reraise_known_errors
def get_requires_for_build_editable(config_settings=None):
  deps = get_requires_for_build_wheel(config_settings, _editable=True)

  # add so incremental virtualenv can be created
  # deps += ['pip', 'virtualenv ~= 20.28.0']
  deps += ['uv ~= 0.8.12']
  return deps

#-----------------------------------------------------------------------------
@_reraise_known_errors
def prepare_metadata_for_build_editable(
  metadata_directory,
  config_settings = None ):

  return prepare_metadata_for_build_wheel(
    metadata_directory,
    config_settings,
    _editable = True)

#-----------------------------------------------------------------------------
@_reraise_known_errors
def build_editable(
  wheel_directory,
  config_settings = None,
  metadata_directory = None ):

  # TODO: save config_settings in staging directory so that rebuilds are consistent
  pyproj = backend_init(
    config_settings = config_settings,
    editable = True)

  editable_root = pyproj.editable_root
  whl_root = editable_root/'wheel'
  venv_dir = editable_root/'build_venv'

  if editable_root.exists():
    # TODO: add status file to avoid accidentally deleting the wrong directory
    shutil.rmtree(editable_root)

  whl_root.mkdir(0o700, parents=True)

  if not any(target.enabled for target in pyproj.targets):
    # not targets need building
    pyproj.dist_prep()
    pyproj.dist_binary_prep()

  else:
    # NOTE: this should clone the current build environment packages to reproduce
    # during incremental builds
    # TODO: use constraints file instead?
    requirements_file = editable_root/'build_requirements.txt'

    # get build dependencies, pinned to version currently installed.
    # keys are PEP 503 normalized names so that lookups match regardless of
    # how the name was spelled in build_requires vs. the installed package.
    env_reqs = {
      norm_dist_name(pkg.req.name): pkg.req
      for pkg in [PkgInfoReq(dep) for dep in pyproj.env_pkgs]}

    build_deps = []

    for dep in pyproj.build_requires:
      build_deps.append(str(dep.req))

      req = env_reqs.get(norm_dist_name(dep.req.name))

      if req is not None:
        build_deps.append(str(req))

    requirements_file.write_text('\n'.join(build_deps))

    if not venv_dir.exists():
      check_call([
        'uv', 'venv', str(venv_dir),
        '--no-project',
        '--python', sys.executable])

    _run_editable_cmd(
      venv_dir,
      ['uv', 'pip', 'install', '--reinstall', '-r', str(requirements_file)])

    _run_editable_py(
      venv_dir,
      ['-I', '-m', 'partis.pyproj.cli', 'prep', str(pyproj.root)])

  with dist_binary_editable(
    root = pyproj.root,
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

    # generate metadata
    record_hash = dist.finalize(metadata_directory)


  pyproj.logger.debug(
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

#===============================================================================
def _run_editable_cmd(venv_dir, args):
  for bin in ['bin', 'Scripts']:
    if (venv_bin := venv_dir/bin).is_dir():
      break
  else:
    raise FileNotFoundError(f"No virtual environment bin directory: {venv_dir}")

  venv_env = {
    **os.environ,
    'VIRTUAL_ENV': str(venv_dir),
    'PATH': os.pathsep.join([str(venv_bin)] + os.environ['PATH'].split(os.pathsep))}

  check_call(args, env = venv_env)

#===============================================================================
def _run_editable_py(venv_dir, args):
  for bin in ['bin', 'Scripts']:
    if (venv_bin := venv_dir/bin).is_dir():
      break
  else:
    raise FileNotFoundError(f"No virtual environment bin directory: {venv_dir}")

  venv_py = venv_bin/Path(sys.executable).name

  if not (venv_py := venv_bin/Path(sys.executable).name).exists():
    raise FileNotFoundError(f"No virtual environment interpreter: {venv_py}")

  venv_env = {
    **os.environ,
    'VIRTUAL_ENV': str(venv_dir),
    'PATH': os.pathsep.join([str(venv_bin)] + os.environ['PATH'].split(os.pathsep))}

  check_call([str(venv_py), *args], env = venv_env)
