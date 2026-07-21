find_package(yaml-cpp REQUIRED)

# Header-only — no VdyRunner, so nothing to implement here.
add_library(vdy_common INTERFACE)
target_include_directories(vdy_common INTERFACE
    # PROJECT_SOURCE_DIR, not CMAKE_SOURCE_DIR - plan.md item 13, see the
    # identical fix/comment in modules/df/src/component/common/CMakeLists.txt.
    ${PROJECT_SOURCE_DIR}/src
    ${PROJECT_SOURCE_DIR}/include
)
target_link_libraries(vdy_common INTERFACE
    AdasInterfaces::AdasInterfaces
    yaml-cpp::yaml-cpp
)
