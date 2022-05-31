from partis.utils.sphinx import basic_main

import os
import os.path as osp

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
if __name__ == "__main__":

  conf_dir = osp.abspath( osp.dirname(__file__) )
  root_dir = osp.abspath( osp.join( conf_dir, os.pardir ) )

  basic_main(
    package = 'partis-pyproj',
    conf_dir = conf_dir,
    src_dir = conf_dir,
    root_dir = root_dir )
