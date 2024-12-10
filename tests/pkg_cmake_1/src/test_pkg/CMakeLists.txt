add_custom_command(
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/plat_mod.c
  COMMAND ${Python3_EXECUTABLE} -m cython --fast-fail -o ${CMAKE_CURRENT_BINARY_DIR}/plat_mod.c ${CMAKE_CURRENT_SOURCE_DIR}/plat_mod.pyx
  DEPENDS plat_mod.pyx )

python3_add_library( test_pkg_mod MODULE WITH_SOABI
  plat_mod.c )

install(
  TARGETS test_pkg_mod 
  LIBRARY DESTINATION lib )