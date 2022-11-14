cmake_minimum_required(VERSION 3.17)

project(test_pkg
  VERSION 1.2.3
  DESCRIPTION "Test Package for partis.pyproj"
  LANGUAGES C )

option(opt_a "Build option opt_a" ON)

set(CMAKE_C_STANDARD 99)

set(Python3_FIND_STRATEGY LOCATION)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

add_custom_command(
  OUTPUT ${CMAKE_CURRENT_SOURCE_DIR}/src/test_pkg/plat_mod.c
  COMMAND ${Python3_EXECUTABLE} -m cython ${CMAKE_CURRENT_SOURCE_DIR}/src/test_pkg/plat_mod.pyx
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/src
  DEPENDS
    ${CMAKE_CURRENT_SOURCE_DIR}/src/test_pkg/plat_mod.pyx )

Python3_add_library(test_pkg_mod
  ${CMAKE_CURRENT_SOURCE_DIR}/src/test_pkg/plat_mod.c )

install(
  TARGETS test_pkg_mod
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} )