from pytest import (
  raises )
from partis.pyproj import (
  ValidationError)
from partis.pyproj.pptoml import (
  dependency_groups)

#===============================================================================
def test_dependency_groups():
  # https://packaging.python.org/en/latest/specifications/dependency-groups/
  group = dependency_groups({
    'test': ["pytest>7", "coverage"]})

  group = dependency_groups({
    'coverage': ["coverage[toml]"],
    'test': ["pytest>7", {'include-group': "coverage"}]})

  assert group['test'][1]['include-group'] == 'coverage'

  with raises(ValidationError):
    # has to be mapping
    dependency_groups([])

  with raises(ValidationError):
    dependency_groups('foo')

  with raises(ValidationError):
    # has to be *list* of dependencies
    dependency_groups({'foo': 'asd'})

  with raises(ValidationError):
    # mappings only allow "include-group" key
    dependency_groups({'foo': {'bar': 'abc'}})

  with raises(ValidationError):
    # include groups have to exist
    dependency_groups({'foo': ['abc'], 'bar': [{'include-group': "xyz"}]})

  with raises(ValidationError):
    # include groups cannot be recursive
    dependency_groups({'foo': [{'include-group': "foo"}]})

#===============================================================================
if __name__ == '__main__':
  test_dependency_groups()
