# Test configuration for Mode S decoder
cmake_minimum_required(VERSION 3.16)

# Enable testing
enable_testing()

# Find or fetch Google Test
include(FetchContent)
FetchContent_Declare(
    googletest
    GIT_REPOSITORY https://github.com/google/googletest.git
    GIT_TAG v1.14.0
)
# For Windows: Prevent overriding the parent project's compiler/linker settings
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# CRC tests
add_executable(test_crc test_crc.cpp)
target_link_libraries(test_crc PRIVATE modes GTest::gtest_main)
target_include_directories(test_crc PRIVATE ${CMAKE_SOURCE_DIR}/include)

# Decoder tests
add_executable(test_decoder test_decoder.cpp)
target_link_libraries(test_decoder PRIVATE modes GTest::gtest_main)
target_include_directories(test_decoder PRIVATE ${CMAKE_SOURCE_DIR}/include)

# CPR tests
add_executable(test_cpr test_cpr.cpp)
target_link_libraries(test_cpr PRIVATE modes GTest::gtest_main)
target_include_directories(test_cpr PRIVATE ${CMAKE_SOURCE_DIR}/include)

# End-to-end validation against published, known-correct ADS-B examples.
add_executable(validation_test validation_test.cpp)
target_link_libraries(validation_test PRIVATE modes GTest::gtest_main)
target_include_directories(validation_test PRIVATE ${CMAKE_SOURCE_DIR}/include)

# Register tests with CTest
include(GoogleTest)
gtest_discover_tests(test_crc)
gtest_discover_tests(test_decoder)
gtest_discover_tests(test_cpr)
gtest_discover_tests(validation_test)
