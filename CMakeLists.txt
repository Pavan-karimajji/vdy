cmake_minimum_required(VERSION 3.22)
project(adas-vdy VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)

if(NOT DEFINED TARGET_TYPE)
    set(TARGET_TYPE sil CACHE STRING "Build target: sil, autosar")
endif()

# Accepted for parity with build.bat's <project> argument / the project-
# variant model (build.bat always passes -DADAS_PROJECT=%PROJECT%) and for
# forward-compat with a future compile-time-baked path, same axis df's own
# ADAS_PROJECT serves. Unlike df, nothing in vdy's own CMakeLists currently
# consumes it — vdy's src/project/<name>/ego_params.yaml is read purely at
# runtime, by whatever path a caller (a test, later a real function) supplies
# to ParamLoader directly — no compile-time path-baking exists here (or is
# needed) yet.
if(NOT DEFINED ADAS_PROJECT)
    set(ADAS_PROJECT base CACHE STRING "Which src/project/<name> calibration folder this build is associated with, e.g. base, cus1")
endif()

find_package(AdasInterfaces REQUIRED)

add_subdirectory(src/component)

if(TARGET_TYPE STREQUAL "sil")
    add_subdirectory(src/platform/vdy_sil)
elseif(TARGET_TYPE STREQUAL "autosar")
    add_subdirectory(src/platform/autosar)
elseif(TARGET_TYPE STREQUAL "standalone")
    add_subdirectory(src/platform/standalone)
endif()

if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(tests)
endif()
