import os
import tempfile
import logging

import pytest

from partis.pyproj.file import tail
from partis.pyproj.builder.process import process
from partis.pyproj.validate import ValidPathError


class DummyRunner:
    def __init__(self):
        self.commands = []

    def run(self, cmd):
        self.commands.append(cmd)


def test_tail_basic_and_bufsize():
    # create a temporary file with multiple lines
    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.write("a\n" + "b\n" + "c\n")
        name = tmp.name

    try:
        # requesting more lines than available should return all lines
        assert tail(name, 10) == ["a", "b", "c", ""]
        # requesting last two lines with small buffer to force multiple reads
        assert tail(name, 2, bufsize=2) == ["c", ""]
    finally:
        os.unlink(name)


def test_tail_zero_or_negative():
    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.write("x\ny\n")
        name = tmp.name
    try:
        assert tail(name, 0) == [""]
        assert tail(name, -5) == [""]
    finally:
        os.unlink(name)


def test_process_branches(tmp_path):
    logger = logging.getLogger("test")
    work = tmp_path / "work"
    src = tmp_path / "src"
    prefix = tmp_path / "prefix"
    build = tmp_path / "build"

    for p in (work, src, prefix, build):
        p.mkdir()

    runner = DummyRunner()
    # empty build dir: all commands executed
    process(None, logger, {}, work, src, build, prefix,
            ["setup"], ["compile"], ["install"], True, runner)
    assert runner.commands == [["setup"], ["compile"], ["install"]]

    # non-empty build dir with build_clean False: setup skipped
    (build / "marker").write_text("x")
    runner2 = DummyRunner()
    process(None, logger, {}, work, src, build, prefix,
            ["setup"], ["compile"], ["install"], False, runner2)
    assert runner2.commands == [["compile"], ["install"]]

    # build_clean True with non-empty dir raises error
    with pytest.raises(ValidPathError):
        process(None, logger, {}, work, src, build, prefix,
                ["setup"], ["compile"], ["install"], True, DummyRunner())
