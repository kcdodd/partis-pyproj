import os
import os.path as osp
import sys
import importlib
from pathlib import Path

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

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class EntryPointError(ValueError):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def module_name_from_path( path, root ):
  """Generates an importable module name from a file system path

  Parameters
  ----------
  path : str
    Path to the module directory relative to 'root'
  root : str
    Base path from which the module will be imported
  """
  path = Path( path )
  root = Path( root )

  # path = path.with_suffix("")

  relative_path = osp.relpath( path, start = root )

  path_parts = Path(relative_path).parts

  if len(path_parts) == 0:
    raise EntryPointError("Empty module name")

  return ".".join(path_parts)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def load_module( path, root ):

  if not osp.isdir(path):
    raise EntryPointError(f"Not a directory: {path}")

  init_file = osp.join( path, "__init__.py" )

  if not osp.isfile(init_file):
    raise EntryPointError(f"Not a module: {init_file}")

  module_name = module_name_from_path( path = path, root = root )

  spec = importlib.util.spec_from_file_location(
    name = module_name,
    location = str(init_file) )

  mod = importlib.util.module_from_spec( spec )
  sys.modules[ spec.name ] = mod

  spec.loader.exec_module( mod )

  return mod

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def load_entrypoint( entry_point, root ):

  mod_name, attr_name = entry_point.split(':')

  mod_name = mod_name.strip()
  attr_name = attr_name.strip()

  mod = load_module(
    path = osp.join( root, norm_path_to_os( mod_name.replace('.', '/') ) ),
    root = root )

  if not hasattr( mod, attr_name ):
    raise EntryPointError(
      f"'{mod_name}' :'{attr_name}'" )

  func = getattr( mod, attr_name )

  return func

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class EntryPoint:
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
        entry = entry,
        root = root )

      logger.info(f"loaded entry-point '{entry}'")

    except Exception as e:
      raise EntryPointError(f"failed to load '{entry}'") from e

  #-----------------------------------------------------------------------------
  def __call__(self, **kwargs):

    cwd = os.getcwd()

    try:

      with validating( file = f"{self.name} -> {self.entry}(**{{{kwargs}}})" ):
        self.func(
          self.pyproj,
          logger = self.logger,
          **kwargs )

    except Exception as e:
      raise EntryPointError(f"failed to run '{self.entry}'") from e

    finally:
      os.chdir(cwd)
