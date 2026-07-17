cmake_minimum_required(VERSION 3.22)

find_package(GTest QUIET)

if(NOT GTest_FOUND)
    message(STATUS "GTest not found locally. Fetching GoogleTest from GitHub...")
    include(FetchContent)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
    )
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googletest)
endif()

add_executable(vdy_tests
    unit/test_vdy_function.cpp
    unit/test_param_loader.cpp
)

find_package(AdasSharedConfig REQUIRED)

target_compile_definitions(vdy_tests PRIVATE
    ADAS_VDY_TEST_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures"
    ADAS_VDY_SHARED_CONFIG_DIR="${adas-shared-config_PACKAGE_FOLDER_RELEASE}/projects"
)

target_link_libraries(vdy_tests PRIVATE
    vdy_function
    vdy_sil
    GTest::gtest_main
)

add_custom_command(TARGET vdy_tests POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        $<TARGET_FILE:vdy_sil>
        $<TARGET_FILE_DIR:vdy_tests>
)

include(GoogleTest)
gtest_discover_tests(vdy_tests)
