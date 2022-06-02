project( 'test_pkg',
  'cython',
  'c',
  version : '1.2.3',
  license : '',
  meson_version: '>= 0.60'  )

#...............................................................................
# https://mesonbuild.com/Python-module.html
py_mod = import('python')
py3 = py_mod.find_installation('python3')

if py3.found() and not py3.language_version().version_compare('>= 3.6')
  error('Python 3.6 or newer is required.')
endif

py3_dep = dependency(
  'python3',
  required : true )

py3.extension_module(
  'plat_mod',
  'src/test_pkg/plat_mod.pyx',
  dependencies : py3_dep,
  install: true,
  install_dir : 'lib' )
