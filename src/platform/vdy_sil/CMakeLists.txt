add_library(vdy_sil SHARED
    vdy_interface_c.cpp
    param_loader.cpp
)
target_compile_definitions(vdy_sil PRIVATE VDY_SIL_EXPORTS)
target_include_directories(vdy_sil PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(vdy_sil PRIVATE vdy_function)
