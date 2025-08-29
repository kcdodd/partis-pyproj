from __future__ import annotations
from pathlib import Path
from string import Template
import tempfile
from importlib.metadata import metadata
from partis.pyproj.path import (
  PathFilter)

#===============================================================================
def _init_parser(subparsers):

  parser = subparsers.add_parser(
    'init',
    help='Initialize template pyproject.toml')

  parser.add_argument(
    '--name',
    type=str,
    default=None,
    help='Project name')

  parser.add_argument(
    '--version',
    type=str,
    default='0.0.1',
    help='Initial project version')

  parser.add_argument(
    '--desc',
    type=str,
    default='',
    help='Project short description')

  parser.add_argument(
    'path',
    type=Path,
    help='Path of directory to create pyproject.toml')

  parser.set_defaults(func = _init_impl)

  return parser

#===============================================================================
def _init_impl(args):
  _init_pyproj(
    path = args.path,
    project = args.name,
    version = args.version,
    description = args.desc)

#===============================================================================
def _init_pyproj(
    path: Path,
    project: str|None,
    version: str,
    description: str):

  pyproj_version = metadata('partis-pyproj')['version']

  root: Path = path.resolve()
  pptoml_file = root/'pyproject.toml'
  readme_file: str = None
  license_file: str = None
  copy_sources: list[str] = []

  if not root.exists():
    root.mkdir()

  elif not root.is_dir():
    raise FileExistsError(f"Project is not a directory: {root}")

  if pptoml_file.exists():
    raise FileExistsError(f"Project already exists: {pptoml_file}")

  if project is None:
    project = root.name

  if not description:
    description = f"Package for {project}"

  dependencies = []
  ignore_patterns = [
    '.git/',
    '.gitignore',
    '__pycache__',
    '*.py[cod]',
    '*.so',
    '*.egg-info',
    '.nox',
    '.pytest_cache',
    '.coverage']

  if (ignore_file := root/'.gitignore').exists():
    lines = [
      line.strip()
      for line in ignore_file.read_text().splitlines()]

    lines = [
      line
      for line in lines
      if line and not line.startswith('#')]

    ignore_patterns.extend(lines)

  # make unique, keep order
  ignore_patterns = list({k:None for k in ignore_patterns})

  filter = PathFilter(ignore_patterns, start=root)
  fnames = [file.name for file in root.iterdir() if file.is_file()]
  dnames = [file.name for file in root.iterdir() if file.is_dir()]
  ignored = filter.filter(root, fnames, dnames)
  names = [name for name in fnames+dnames if name not in ignored]

  for name in names:
    if name.upper().startswith('README'):
      readme_file = name
    elif name.upper().startswith('LICENSE'):
      license_file = name
    elif name == 'requirements.txt':
      dependencies.extend([
        dep.strip()
        for dep in Path(root/name).read_text().splitlines()])
    else:
      copy_sources.append(name)

  if not readme_file:
    readme_file = 'README.md'

  if not license_file:
    license_file = 'LICENSE.txt'

  purelib = [
    file.parent.relative_to(root)
    for file in root.glob(f'**/{project}/__init__.py')]

  dependencies = [
    dep
    for dep in dependencies
    if dep and not dep.startswith('#')]

  # print(f"project.readme.file: {readme_file}")
  # print(f"project.license.file: {license_file}")
  # print("tool.pyproj.dist.source:")

  # for name in copy_sources:
  #   print(f" {name}")

  pptoml = Template(BASE).substitute(
    pyproj_version = str(pyproj_version),
    project=project,
    version=version,
    description=description,
    license_file=license_file,
    readme_file=readme_file,
    dependencies = ',\n'.join([f"  {dep!r}" for dep in dependencies]),
    sources = ',\n'.join([f"  '{name}'" for name in copy_sources]),
    purelib = ',\n'.join([f"  {{src = '{name}', dst = '{project}'}}" for name in purelib]))

  print(f"Proposed project: {project} {version} -> {pptoml_file}")
  print('#'*80)
  print(pptoml)
  print('#'*80)

  if not (root/readme_file).exists():
    print(f"+ Will create empty readme file: {readme_file}")

  if not (root/license_file).exists():
    print(f"+ Will create empty license file: {license_file}")


  res = input("Confirm to write project files? [y/n] ")

  if not res.startswith('y'):
    print("Aborting...")
    return

  if not (root/readme_file).exists():
    print(f"Writing empty readme file: {readme_file}")
    (root/readme_file).write_text(description)

  if not (root/license_file).exists():
    print(f"Writing empty license file: {license_file}")
    (root/license_file).write_text('')

  print(f"Writing project file: {pptoml_file}")
  pptoml_file.write_text(pptoml)

#===============================================================================
BASE = """
[project]
name = "${project}"
description = "${description}"
version = "${version}"
readme = { file = "${readme_file}" }
license = { file = "${license_file}" }

requires-python = ">= 3.8"
dependencies = [
${dependencies}
]

#-------------------------------------------------------------------------------
[build-system]
requires = ["partis-pyproj ~= ${pyproj_version}"]
build-backend = "partis.pyproj.backend"

#-------------------------------------------------------------------------------
[tool.pyproj.dist]

ignore = [
  '__pycache__',
  '*.py[cod]',
  '*.so',
  '*.egg-info',
  '.nox',
  '.pytest_cache',
  '.coverage']

#...............................................................................
[tool.pyproj.dist.source]
copy = [
${sources}
]

#...............................................................................
[tool.pyproj.dist.binary.purelib]
copy = [
${purelib}
]

#...............................................................................
[tool.pyproj.dist.binary.platlib]
copy = [
]
"""