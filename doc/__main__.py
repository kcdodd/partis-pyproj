import re
import subprocess
from pathlib import Path
from partis.pyproj import (
  norm_dist_name,
  join_dist_filename,
  dist_targz )
from . import conf

#===============================================================================
if __name__ == "__main__":

  conf_dir = Path(__file__).parent
  root_dir = conf_dir.parent
  project_normed = re.sub(r'[^\w]+', '_', conf.project_normed.strip() ).lstrip('_')
  project_filename = join_dist_filename( [project_normed, conf.version] )
  dist_name = project_filename
  doc_dist_name = dist_name + '-doc'
  doc_dist_file = doc_dist_name + '.tar.gz'

  src_dir = conf_dir
  builder_dir = root_dir/'build/html'

  cmd = [
    'python3',
    '-m',
    'sphinx.cmd.build',
    '-T',
    '-b',
    'html',
    str(src_dir),
    str(builder_dir),
    '-c',
    str(conf_dir) ]

  print('> ', ' '.join(cmd))
  subprocess.check_call(cmd)

  with dist_targz(
    outname = doc_dist_file,
    outdir = root_dir/'dist') as dist:

    dist.copytree(
      src = builder_dir,
      dst = '/'.join([doc_dist_name, 'html']))