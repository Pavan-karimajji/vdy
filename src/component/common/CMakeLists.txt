find_package(yaml-cpp REQUIRED)

# Header-only — no VdyRunner, so nothing to implement here.
add_library(vdy_common INTERFACE)
target_include_directories(vdy_common INTERFACE
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_SOURCE_DIR}/include
)
target_link_libraries(vdy_common INTERFACE
    AdasInterfaces::AdasInterfaces
    yaml-cpp::yaml-cpp
)
