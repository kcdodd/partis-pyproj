from copy import copy
from pathlib import Path

import pytest

from partis.pyproj import Namespace, template_substitute, FileOutsideRootError
from partis.pyproj.template import Template, TemplateError, NamespaceError


def test_namespace_copy_and_dirs(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    ns = Namespace({"root": root, "ext": external, "name": "abc"}, root=root, dirs=[external])
    # path outside root but within allowed dirs
    path = ns["root/../ext/'file.txt'"]
    assert path == external / "file.txt"
    # ensure copy is independent
    ns2 = copy(ns)
    ns2["name"] = "xyz"
    assert ns2["name"] == "xyz"
    assert ns["name"] == "abc"
    # outside allowed dirs should raise
    with pytest.raises(FileOutsideRootError):
        ns["root/../'notallowed'/'file'"]


def test_substitute_kwargs_only():
    result = Template("${X}").substitute(X=10)
    assert result == "10"


def test_substitute_both_namespace_and_kwargs_raises():
    with pytest.raises(TypeError, match="Cannot use both namespace and kwargs"):
        Template("${X}").substitute({'X': 1}, Y=10)


def test_substitute_plain_dict_wraps_as_namespace():
    result = Template("${X}").substitute({'X': 10})
    assert result == "10"


def test_namespace_dirs_single_path():
    d = Path('/some/dir')
    ns = Namespace({}, dirs=d)
    assert ns.dirs == [d]


def test_namespace_iter_and_len():
    ns = Namespace({'A': 1, 'B': 2})
    assert set(iter(ns)) == {'A', 'B'}
    assert len(ns) == 2


def test_namespace_root_none_path_construction():
    ns = Namespace({'dir': 'subdir'}, root=None)
    result = ns["dir/'file.txt'"]
    assert result == Path('subdir', 'file.txt')


def test_namespace_nested_attr_on_scalar_raises():
    ns = Namespace({'X': 42})
    with pytest.raises(NamespaceError):
        ns['X.Y']


def test_template_substitute_nested(tmp_path):
    ns = {"name": "world", "num": 5, "dir": tmp_path}
    value = {
        "greet": "Hello ${name}",
        "path": tmp_path / "${name}",
        "items": ["${num}", {"inner": "${name}"}],
    }
    result = template_substitute(value, ns)
    assert result["greet"] == "Hello world"
    assert result["path"] == tmp_path / "world"
    assert result["items"][0] == "5"
    assert result["items"][1]["inner"] == "world"
