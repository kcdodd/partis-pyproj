import os
import os.path as osp
import tempfile
import shutil
from pathlib import (
  Path,
  PurePosixPath)

from pytest import (
  raises )

from partis.pyproj import (
  Template,
  Namespace,
  template_substitute)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def test_template():
  root = PurePosixPath('/root')

  namespace = Namespace(
    { 'plain': 'simple',
      'a': {
      'b': {
        'c': 'xyz',
        'd': ['qwe']}},
     'project': {
       'name': 'my_project'},
     'prefix': root/'tmp'},
    root = root)

  valid_cases = [
    ("${plain}", "simple"),
    ("${a.b.c}", "xyz"),
    ("${a.b.d[0]}", "qwe"),
    ("${a.b.d[-1]}", "qwe"),
    ("${a.b.d}", "['qwe']"),
    ("${/'wxyz'}", "/root/wxyz"),
    ("${prefix/project.name/a.b.c/'xyz'/'abc.so'}", "/root/tmp/my_project/xyz/xyz/abc.so")]

  for tmpl, expected in valid_cases:
    value = Template(tmpl).substitute(namespace)
    # print(f"{tmpl} -> {value}")
    assert expected == value

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
if __name__ == '__main__':
  test_template()
