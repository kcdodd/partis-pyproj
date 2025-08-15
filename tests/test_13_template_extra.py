from copy import copy
from pathlib import Path

import pytest

from partis.pyproj import Namespace, template_substitute, FileOutsideRootError


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
