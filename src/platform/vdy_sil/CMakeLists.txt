add_library(vdy_sil SHARED
    vdy_interface_c.cpp
    param_loader.cpp
)
target_compile_definitions(vdy_sil PRIVATE VDY_SIL_EXPORTS)
target_include_directories(vdy_sil PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(vdy_sil PRIVATE vdy_function)

# plan.md item 13 (docs/build_superbuild_aggregator_plan.md §3) - lets a
# consumer link "AdasVdy::AdasVdy" whether vdy is in-tree (this alias, via the
# superproject aggregator's add_subdirectory) or a real Conan package
# (find_package's own same-named imported target) - zero branching in any
# consumer's CMakeLists.txt either way.
add_library(AdasVdy::AdasVdy ALIAS vdy_sil)

# Needed for a real `conan create` package (plan.md item 14) - the SIL DLL
# deliverable, same pattern as adas-interfaces' own install() (plan.md item 13).
install(TARGETS vdy_sil
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)
install(FILES vdy_interface_c.h DESTINATION include)
