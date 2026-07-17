add_subdirectory(common)

add_library(vdy_function STATIC
    vdy_function.cpp
)
target_link_libraries(vdy_function PUBLIC vdy_common)
