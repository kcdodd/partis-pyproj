project( 'test_pkg',
  'cython',
  'c',
  version : '1.2.3',
  license : '',
  meson_version: '>= 0.60'  )

#...............................................................................
# https://mesonbuild.com/Python-module.html
py_mod = import('python')
# NOTE: no name/path argument -> meson uses the interpreter it is running under
# (the build environment's python). Passing 'python3' searches PATH, which fails
# in Windows venvs and pip build-env overlays: they contain python.exe but no
# python3.exe, so the name resolves to an unrelated interpreter.
py3 = py_mod.find_installation()

if py3.found() and not py3.language_version().version_compare('>= 3.6')
  error('Python 3.6 or newer is required.')
endif

py3_dep = py3.dependency( required : true )

py3.extension_module(
  'plat_mod',
  'src/test_pkg/plat_mod.pyx',
  dependencies : py3_dep,
  install: true,
  install_dir : 'lib' )
