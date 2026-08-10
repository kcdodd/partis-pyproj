import pytest
from partis.pyproj import cache

#===============================================================================
@pytest.fixture(autouse = True)
def isolate_cache_dir(tmp_path_factory, monkeypatch):
  """Keep the user cache out of the test suite

  The editable build environment is created under ``cache_dir()`` and out-lives a
  single build, so a test that builds an editable distribution would otherwise
  leave a virtual environment in the real user cache, keyed on a temporary
  directory that no longer exists.
  """
  cache_dir = tmp_path_factory.mktemp('cache')

  # NOTE: the environment variable is for any 'partis-pyproj' sub-process, the
  # module value for the test process itself
  monkeypatch.setenv('PARTIS_PYPROJ_CACHE_DIR', str(cache_dir))
  monkeypatch.setattr(cache, 'CACHE_DIR', cache_dir)
