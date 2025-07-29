import logging
from pathlib import Path

from partis.pyproj.pptoml import pyproj_dist_copy
from partis.pyproj.dist_file.dist_copy import dist_iter


def test_dist_iter_strip_and_replace(tmp_path):
    src = tmp_path / "src"
    sub = src / "sub"
    sub.mkdir(parents=True)
    file_path = sub / "original.txt"
    file_path.write_text("data")

    copy_item = pyproj_dist_copy({
        'src': src,
        'dst': Path('dest'),
        'include': [
            {
                'glob': 'sub/*.txt',
                'rematch': r'(.*)\.txt',
                'replace': '{1}.dat',
                'strip': 1,
            }
        ]
    })

    items = list(dist_iter(
        copy_items=[copy_item],
        ignore=[],
        root=tmp_path,
        logger=logging.getLogger(__name__),
    ))

    assert len(items) == 1
    _, src_file, dst_file, _, individual = items[0]
    assert src_file == file_path
    assert dst_file == Path('dest') / 'original.dat'
    assert not individual
