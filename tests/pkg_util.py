"""Shared helpers for the corpus of test packages (``tests/pkg_*``)

The corpus declares ``partis-pyproj`` in ``build-system.requires`` without a
version, and every fixture is copied before use with that requirement pinned to
the installed version, which is also the version built into ``dist/``.

A build-isolated front-end resolves ``build-system.requires`` in a fresh
environment, so the requirement decides which ``partis-pyproj`` actually builds
the fixture. A hard-coded pin goes stale on every version bump, and no pin at
all silently selects the newest *released* version instead of the version under
test.
"""
from __future__ import annotations
import re
import shutil
from pathlib import Path
from importlib import metadata

# matches a 'partis-pyproj' requirement string, e.g. '"partis-pyproj[meson] >= 0.2"'
PYPROJ_REQ = re.compile(
  r'(?P<q>["\'])(?P<name>partis-pyproj)(?P<extras>\[[^\]]*\])?(?P<spec>[^"\']*)(?P=q)')

#===============================================================================
def pin_pyproj_req(pptoml_file: Path, version: str|None = None) -> str:
  """Pins the 'partis-pyproj' build requirement of a 'pyproject.toml', in place

  Parameters
  ----------
  pptoml_file:
    Path to the 'pyproject.toml' to update.
  version:
    Version to pin to, defaulting to the installed version.

  Returns
  -------
  version:
    The version pinned to.
  """

  if version is None:
    version = metadata.version('partis-pyproj')

  text = pptoml_file.read_text()

  text, nsub = PYPROJ_REQ.subn(
    lambda m: f"{m['q']}{m['name']}{m['extras'] or ''} == {version}{m['q']}",
    text)

  if nsub == 0:
    raise ValueError(
      f"'partis-pyproj' build requirement not found: {pptoml_file}")

  pptoml_file.write_text(text)

  return version

#===============================================================================
def copy_pkg(src: Path, dst: Path, version: str|None = None) -> Path:
  """Copies a test package, pinning its 'partis-pyproj' build requirement

  Parameters
  ----------
  src:
    Directory of the test package to copy.
  dst:
    Directory to copy into, must not already exist.
  version:
    Version to pin to, defaulting to the installed version.
  """

  # NOTE: some tests require copying symlinks
  shutil.copytree(src, dst, symlinks = True)

  pin_pyproj_req(dst/'pyproject.toml', version)

  return Path(dst)
