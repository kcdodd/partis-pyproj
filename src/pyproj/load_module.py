from __future__ import annotations
import os
import os.path as osp
import sys
import importlib
from pathlib import (
  Path,
  PurePath,
  PurePosixPath)
import hashlib
from base64 import b16encode

from .norms import (
  norm_path_to_os )

from .validate import (
  ValidationWarning,
  ValidationError,
  FileOutsideRootError,
  valid_dict,
  validating,
  valid,
  restrict,
  mapget )

#===============================================================================
class EntryPointError(ValidationError):
  pass

#===============================================================================
def module_name_from_path( path, root ):
  """Generates an importable module name from a file system path

  Parameters
  ----------
  path : pathlib.Path
    Path to the module directory relative to 'root'
  root : pathlib.Path
    Base path from which the module will be imported
  """

  path_parts = path.relative_to(root).parts

  if len(path_parts) == 0:
    raise EntryPointError("Empty module name")

  return ".".join(path_parts)

#===============================================================================
def module_path( mod_name, root ):
  path = root / Path(*mod_name.split('.'))

  if path.exists() and path.is_dir():
    path /= '__init__.py'
  else:
    path = path.with_suffix('.py')

  if not path.exists():
    path = None

  return path

#===============================================================================
def load_module( name, path, root ):

  path = str(path)

  # TODO: handle module names when module is not directly in 'root'.
  hasher = hashlib.sha256()
  hasher.update( path.encode('utf-8') )
  digest = hasher.digest()

  _prefix = 'pyprojentry_' + b16encode(digest).decode('ascii')

  spec = importlib.util.spec_from_file_location(
    name = _prefix + name,
    location = path )

  mod = importlib.util.module_from_spec( spec )
  sys.modules[ spec.name ] = mod

  spec.loader.exec_module( mod )

  return mod

#===============================================================================
def load_entrypoint( entry_point, root ):
  r"""
  Parameters
  ----------
  entry_point : str
    Entry point spec
  root : pathlib.Path
    Root project directory.
  """

  mod_name, attr_name = entry_point.split(':')

  mod_name = mod_name.strip()
  attr_name = attr_name.strip()

  mod_path = module_path(mod_name, root)

  if mod_path is None:
    try:
      mod = importlib.import_module(mod_name)

    except ImportError as e:
      raise EntryPointError(f"failed to load '{entry_point}'") from e

  else:
    try:
      mod = load_module(
        name = mod_name,
        path = mod_path,
        root = root )

    except EntryPointError as e:
      raise

    except Exception as e:
      raise EntryPointError(f"failed to load '{entry_point}'") from e


  if not hasattr( mod, attr_name ):
    raise EntryPointError(
      f"Loaded module '{mod_name}' does not have attribute: '{attr_name}'" )

  func = getattr( mod, attr_name )

  return func

#===============================================================================
class EntryPoint:
  r"""

  Parameters
  ----------
  pyproj : PyProjBase
  root : pathlib.Path
    Root project directory.
  name : str
    A name for this entry point
  logger : logging.Logger
  entry : str
    Entry point spec

    * https://packaging.python.org/en/latest/specifications/entry-points/
  """

  #-----------------------------------------------------------------------------
  def __init__( self,
    pyproj,
    root,
    name,
    logger,
    entry ):

    self.pyproj = pyproj
    self.root = root
    self.name = name
    self.logger = logger
    self.entry = entry

    try:
      self.func = load_entrypoint(
        entry_point = entry,
        root = root )

      logger.info(f"loaded entry-point '{entry}'")

    except Exception as e:
      raise EntryPointError(f"failed to load '{entry}'") from e

  #-----------------------------------------------------------------------------
  def __call__(self, **kwargs):

    cwd = os.getcwd()

    with validating( file = f"{self.name} -> {self.entry}" ):
      try:
        self.func(
          self.pyproj,
          logger = self.logger,
          **kwargs)

      except ValidationError:
        raise

      except Exception as e:
        raise EntryPointError(f"failed to run '{self.entry}'") from e

      finally:
        os.chdir(cwd)
