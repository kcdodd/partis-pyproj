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
  template_substitute,
  TemplateError,
  NamespaceError,
  FileOutsideRootError)

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
    ("$${plain}", "${plain}"),
    ("${a.b.c}", "xyz"),
    ("${a.b.d[0]}", "qwe"),
    ("${a.b.d[-1]}", "qwe"),
    ("${a.b.d}", "['qwe']"),
    ("${/'wxyz'}", "/root/wxyz"),
    ("${prefix/project.name/a.b.c/'xyz'/'abc.so'}", "/root/tmp/my_project/xyz/xyz/abc.so")]

  invalid_cases = [
    ("${plain", TemplateError),
    ("${plain..", TemplateError),
    ("${plain/...", TemplateError),
    ("${plain/...}", TemplateError),
    ("${complicated}", NamespaceError),
    ("${/'wxyz'/../..}", FileOutsideRootError),
    ("${/'wxyz'/../../..}", FileOutsideRootError)]

  for tmpl, expected in valid_cases:
    value = Template(tmpl).substitute(namespace)
    # print(f"{tmpl} -> {value}")
    assert expected == value

  for tmpl, cls in invalid_cases:
    with raises(cls):
      Template(tmpl).substitute(namespace)

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
if __name__ == '__main__':
  test_template()
