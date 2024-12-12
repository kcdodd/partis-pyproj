cmake_minimum_required(VERSION 3.17)

project(test_pkg
  VERSION 1.2.3
  DESCRIPTION "Test Package for partis.pyproj"
  LANGUAGES C )

option(opt_a "Build option opt_a" ON)

set(CMAKE_C_STANDARD 99)

set(Python3_FIND_STRATEGY LOCATION)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

if(WIN32 AND ("${CMAKE_C_COMPILER_ID}" STREQUAL "GNU"))
if("${CMAKE_SIZEOF_VOID_P}" EQUAL "8")
  # compiling with Mingw-w64 requires MS_WIN64 to be defined
  add_compile_definitions(MS_WIN64)
else()
endif()
endif()

add_subdirectory("src/test_pkg")