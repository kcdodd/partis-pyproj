import os
import sys
import importlib
from pathlib import Path

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def module_name_from_path( path, root ):
  path = Path( path )
  root = Path( root )

  path = path.with_suffix("")

  try:
    relative_path = path.relative_to(root)
  except ValueError:
    path_parts = path.parts[1:]
  else:
    path_parts = relative_path.parts

  if len(path_parts) == 0:
    return "."

  return ".".join(path_parts)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def load_module( path, root ):

  path = Path( path )
  root = Path( root )

  path = path.resolve()

  if not path.is_dir():
    raise ValueError(f"Not a directory: {path}")

  init_file = path.joinpath( "__init__.py" )

  if not init_file.exists():
    return None

  module_name = module_name_from_path( path = path, root = root )

  try:
    return __import__( module_name )
  except ImportError:
    pass

  spec = importlib.util.spec_from_file_location(
    name = module_name,
    location = str(init_file) )

  mod = importlib.util.module_from_spec( spec )
  sys.modules[ spec.name ] = mod

  spec.loader.exec_module( mod )

  return mod
