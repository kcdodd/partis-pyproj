
#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_prep( self, logger ):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_source_prep( self, logger ):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_binary_prep( self, logger ):
  from packaging.tags import sys_tags

  tag = next(iter(sys_tags()))

  compat_tags = [ ( tag.interpreter, tag.abi, tag.platform ) ]

  return compat_tags
