import os
from pathlib import Path, PurePath
from unittest.mock import patch
import pytest
from partis.pyproj.path.scandir import scandir_recursive, DirInfo
from partis.pyproj.path.match import PathFilter

#===============================================================================
def test_dirinfo_get_list_path(tmp_path):
    (tmp_path / 'subdir').mkdir()
    (tmp_path / 'subdir' / 'file.py').write_text('x')
    info = scandir_recursive(tmp_path)
    result = info.get(['subdir', 'file.py'])
    assert result is not None

#===============================================================================
def test_dirinfo_get_empty_path(tmp_path):
    info = scandir_recursive(tmp_path)
    result = info.get(PurePath())
    assert result is info

#===============================================================================
def test_dirinfo_get_missing_intermediate_dir(tmp_path):
    info = scandir_recursive(tmp_path)
    with pytest.raises(FileNotFoundError):
        info.get(PurePath('nonexistent_dir/file.py'))

#===============================================================================
def test_dirinfo_get_missing_file(tmp_path):
    info = scandir_recursive(tmp_path)
    with pytest.raises(FileNotFoundError):
        info.get(PurePath('missing.py'))

#===============================================================================
def test_dirinfo_str(tmp_path):
    (tmp_path / 'file.txt').write_text('hello')
    (tmp_path / 'subdir').mkdir()
    info = scandir_recursive(tmp_path)
    s = str(info)
    assert s.startswith('DirInfo(')
    assert 'files=' in s
    assert 'dirs=' in s
    assert 'ignore=' in s
    assert 'errors=' in s

#===============================================================================
def test_glob_exclude_single_pathfilter(tmp_path):
    (tmp_path / 'keep.py').write_text('x')
    (tmp_path / 'skip.txt').write_text('x')
    info = scandir_recursive(tmp_path)
    include = PathFilter(['**'], start=PurePath())
    exclude = PathFilter(['*.txt'], start=PurePath())
    results = info.glob(include, exclude=exclude)
    names = [p.name for p, _ in results]
    assert 'keep.py' in names
    assert 'skip.txt' not in names

#===============================================================================
def test_glob_exclude_none(tmp_path):
    (tmp_path / 'file.py').write_text('x')
    info = scandir_recursive(tmp_path)
    include = PathFilter(['**'], start=PurePath())
    results = info.glob(include, exclude=None)
    names = [p.name for p, _ in results]
    assert 'file.py' in names

#===============================================================================
def test_scandir_gitignore(tmp_path):
    (tmp_path / 'kept.py').write_text('x')
    (tmp_path / 'ignored.log').write_text('x')
    gitignore = tmp_path / '.gitignore'
    gitignore.write_text('# comment\n*.log\n')
    info = scandir_recursive(tmp_path, gitignore=True)
    assert info.ignore is not None
    assert '*.log' in info.ignore
    assert not any(line.startswith('#') for line in info.ignore)
    assert 'kept.py' in info.files
    assert 'ignored.log' in info.files

#===============================================================================
def test_scandir_oserror_stored_in_errors(tmp_path):
    with patch('partis.pyproj.path.scandir.os_scandir', side_effect=OSError('permission denied')):
        info = scandir_recursive(tmp_path)
    assert '.' in info.errors
    assert 'permission denied' in info.errors['.']
