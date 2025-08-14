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


def test_tail_basic_and_bufsize(tmp_path):
  file = tmp_path/'out.txt'
  file.write_text("a\nb\nc\n")

  # requesting more lines than available should return all lines
  assert tail(file, 10) == ["a", "b", "c"]
  assert tail(file, 3) == ["a", "b", "c"]
  # requesting last two lines with small buffer to force multiple reads
  assert tail(file, 2, bufsize = 1) == ["b", "c"]
  assert tail(file, 1) == ["c"]
  # zero or negative
  assert tail(file, 0) == []
  assert tail(file, -5) == []


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
