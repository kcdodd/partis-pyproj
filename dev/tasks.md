# Coverage improvement tasks

Baseline: 89% overall (single Python 3.13 run), measured after removing dead
`module_name_from_path` from `dist_file/dist_binary.py`.

Priority: **H**igh / **M**edium / **L**ow
Effort: **S**mall (< 1 hr) / **M**edium (1–3 hr) / **L**arge (3+ hr)

| # | Task file | Files touched | Cover before | Priority | Effort |
|---|-----------|---------------|:---:|:---:|:---:|
| 1 | [task_path_utils.md](task_path_utils.md) | `path/utils.py` | ~~63%~~ **100%** ✓ | H | S |
| 2 | [task_path_match.md](task_path_match.md) | `path/match.py` | ~~80%~~ **100%** ✓ | H | S |
| 3 | [task_builder_errors.md](task_builder_errors.md) | `builder/builder.py` | ~~71%~~ **100%** ✓ | M | M |
| 4 | [task_dist_zip_links.md](task_dist_zip_links.md) | `dist_file/dist_zip.py` | ~~74%~~ **96%** ✓ | M | S |
| 5 | [task_dist_binary.md](task_dist_binary.md) | `dist_file/dist_binary.py` | ~~77%~~ **99%** ✓ | M | M |
| 6 | [task_download.md](task_download.md) | `builder/download.py` | ~~77%~~ **95%** ✓ | L | M |
| 7 | [task_cli_rebuild.md](task_cli_rebuild.md) | `cli/build_pyproj.py` | ~~40%~~ **100%** ✓ | H | L |

## Notes

- Tasks 1 and 2 are pure unit tests — no fixtures, no subprocesses, self-contained.
  Good starting points.
- Task 3 requires a fake build target that fails on demand; medium scaffolding.
- Task 4 is small but verifies a subtle correctness property (symlinks in zip).
<!-- NOTE: symlinks are documented as not supported in wheels, because the wheel
format does not support them. But the symlink logic should be solid and not allow them.
-->
- Task 7 is the largest gap by line count but hardest to test: it requires a real
  editable installation environment. Tackle last.
<!-- NOTE: There is a test, but maybe is missing coverage because the coverage hook
is not installed in the virtual environment where at least one of the commands is run.
-->
- After each task, re-run `nox -s "test-3.13" && nox -s report` to verify coverage
  improved and nothing regressed.
