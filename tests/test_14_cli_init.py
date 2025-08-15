from __future__ import annotations

from pathlib import Path
import sys
import tomli
import pytest
from partis.pyproj.cli.init_pyproj import _init_pyproj
from partis.pyproj.cli import __main__ as cli

#==============================================================================

def _stub_metadata(_pkg: str):
    return {"version": "1.0.0"}

#==============================================================================

def test_init_pyproj_creates_files(tmp_path, monkeypatch):
    project_dir = tmp_path / "sample"
    project_dir.mkdir()
    pkg_dir = project_dir / "sample"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("# pkg init\n")
    (project_dir / "extra.txt").write_text("data")

    monkeypatch.setattr("partis.pyproj.cli.init_pyproj.metadata", _stub_metadata)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "y")

    _init_pyproj(path=project_dir, project="sample", version="0.1.0", description="example")

    pptoml_path = project_dir / "pyproject.toml"
    assert pptoml_path.exists()
    data = tomli.loads(pptoml_path.read_text())
    assert data["project"]["name"] == "sample"
    assert data["project"]["version"] == "0.1.0"
    assert (project_dir / "README.md").exists()
    assert (project_dir / "LICENSE.txt").exists()

#==============================================================================

def test_init_pyproj_abort(tmp_path, monkeypatch):
    project_dir = tmp_path / "abort"
    monkeypatch.setattr("partis.pyproj.cli.init_pyproj.metadata", _stub_metadata)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "n")

    _init_pyproj(path=project_dir, project="abort", version="0.1.0", description="")

    assert not (project_dir / "pyproject.toml").exists()
    assert not (project_dir / "README.md").exists()
    assert not (project_dir / "LICENSE.txt").exists()

#==============================================================================
def test_cli_main_help(tmp_path, monkeypatch):
  def _input(*args, **kwargs):
    assert False

  monkeypatch.setattr("builtins.input", _input)
  monkeypatch.setattr(sys, "argv", ["partis-pyproj"])

  cli.main()

#==============================================================================
def test_cli_main_creates_project(tmp_path, monkeypatch):
    project_dir = tmp_path / "cli_proj"
    monkeypatch.setattr("partis.pyproj.cli.init_pyproj.metadata", _stub_metadata)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "y")
    monkeypatch.setattr(sys, "argv", [
        "partis-pyproj", "init", "--name", "cli_proj", "--version", "2.0.0", "--desc", "cli", str(project_dir)
    ])

    cli.main()

    pptoml_path = project_dir / "pyproject.toml"
    assert pptoml_path.exists()
    data = tomli.loads(pptoml_path.read_text())
    assert data["project"]["name"] == "cli_proj"
    assert data["project"]["version"] == "2.0.0"

#==============================================================================


def test_init_pyproj_defaults(tmp_path, monkeypatch):
    project_dir = tmp_path / "auto"
    monkeypatch.setattr("partis.pyproj.cli.init_pyproj.metadata", _stub_metadata)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "y")

    _init_pyproj(path=project_dir, project=None, version="0.1.0", description="")

    data = tomli.loads((project_dir / "pyproject.toml").read_text())
    assert data["project"]["name"] == "auto"
    assert data["project"]["description"] == "Package for auto"


def test_init_pyproj_description_default_with_name(tmp_path, monkeypatch):
    project_dir = tmp_path / "desc_only"
    project_dir.mkdir()
    monkeypatch.setattr("partis.pyproj.cli.init_pyproj.metadata", _stub_metadata)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "y")

    _init_pyproj(path=project_dir, project="pkg", version="0.1.0", description="")

    data = tomli.loads((project_dir / "pyproject.toml").read_text())
    assert data["project"]["name"] == "pkg"
    assert data["project"]["description"] == "Package for pkg"


def test_init_pyproj_path_not_directory(tmp_path, monkeypatch):
    project_file = tmp_path / "notdir"
    project_file.write_text("data")
    monkeypatch.setattr("partis.pyproj.cli.init_pyproj.metadata", _stub_metadata)

    with pytest.raises(FileExistsError):
        _init_pyproj(path=project_file, project="x", version="0.1.0", description="x")


def test_init_pyproj_existing_pyproject(tmp_path, monkeypatch):
    project_dir = tmp_path / "exists"
    project_dir.mkdir()
    (project_dir / "pyproject.toml").write_text("[project]\nname='exists'\n")
    monkeypatch.setattr("partis.pyproj.cli.init_pyproj.metadata", _stub_metadata)

    with pytest.raises(FileExistsError):
        _init_pyproj(path=project_dir, project="exists", version="0.1.0", description="")


def test_init_pyproj_respects_gitignore(tmp_path, monkeypatch):
    project_dir = tmp_path / "gitignore"
    project_dir.mkdir()
    pkg_dir = project_dir / "gitignore"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("# pkg init\n")
    (project_dir / ".gitignore").write_text("skip.txt\n")
    (project_dir / "skip.txt").write_text("data")
    (project_dir / "keep.txt").write_text("data")

    monkeypatch.setattr("partis.pyproj.cli.init_pyproj.metadata", _stub_metadata)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "y")

    _init_pyproj(path=project_dir, project="gitignore", version="0.1.0", description="gi")

    data = tomli.loads((project_dir / "pyproject.toml").read_text())
    sources = data["tool"]["pyproj"]["dist"]["source"]["copy"]
    assert "keep.txt" in sources
    assert "skip.txt" not in sources


def test_init_pyproj_preserves_existing_readme_and_license(tmp_path, monkeypatch):
    project_dir = tmp_path / "preserve"
    project_dir.mkdir()
    (project_dir / "README.md").write_text("existing readme")
    (project_dir / "LICENSE.txt").write_text("existing license")
    monkeypatch.setattr("partis.pyproj.cli.init_pyproj.metadata", _stub_metadata)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "y")

    _init_pyproj(path=project_dir, project="preserve", version="0.1.0", description="desc")

    assert (project_dir / "README.md").read_text() == "existing readme"
    assert (project_dir / "LICENSE.txt").read_text() == "existing license"


