
from partis.pyproj import (
  PkgInfo )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_simple():
  pkginfo = PkgInfo(
    project = dict(
      name = 'test_pkg',
      version = '1.2.3' ) )
