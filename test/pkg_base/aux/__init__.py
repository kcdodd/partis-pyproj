#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def prep( self, logger ):
  x = self.config['opt_a']
  print(f'config opt_a: {x}')
  assert self.config['opt_b'] == 'xyz'

  self.project.update( version = "0.0.1" )

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_prep( self, logger ):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_source_prep( self, logger ):
  pass

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
def dist_binary_prep( self, logger ):
  self.compat_tags = [('py3', 'none', 'any')]

  self.build_number = 123
  self.build_tag = 'test'
