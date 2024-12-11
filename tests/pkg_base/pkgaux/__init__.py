#===============================================================================
def prep( self, logger ):
  x = self.config_settings.opt_a
  y = self.config_settings.opt_b
  print(f'config opt_a: {x}')
  print(f'config opt_b: {y}')
  assert self.config_settings.opt_b == 'xyz'

  self.project.version = "0.0.1"

#===============================================================================
def dist_prep( self, logger ):
  pass

#===============================================================================
def dist_source_prep( self, logger ):
  pass

#===============================================================================
def dist_binary_prep( self, logger ):
  self.binary.compat_tags = [('py3', 'none', 'any')]
  self.binary.build_number = 123
  self.binary.build_suffix = 'test'
