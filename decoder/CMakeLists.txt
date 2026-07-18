cmake_minimum_required(VERSION 3.16)
project(libmodes VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Compiler warnings
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(-Wall -Wextra -Wpedantic -Werror)
endif()

# Library sources
set(LIB_SOURCES
    src/crc.cpp
    src/decoder.cpp
    src/cpr.cpp
)

# Create static library
add_library(modes STATIC ${LIB_SOURCES})
target_include_directories(modes PUBLIC include)

# Create shared library
add_library(modes_shared SHARED ${LIB_SOURCES})
target_include_directories(modes_shared PUBLIC include)
set_target_properties(modes_shared PROPERTIES OUTPUT_NAME modes)

# CLI tool for testing
add_executable(modes_decode src/main.cpp)
target_link_libraries(modes_decode PRIVATE modes)

# HTTP Server
add_executable(modes_server src/server_main.cpp src/server.cpp)
target_link_libraries(modes_server PRIVATE modes)

# Testing
option(BUILD_TESTS "Build unit tests" ON)
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

# Install targets
install(TARGETS modes modes_shared modes_decode modes_server
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)
install(DIRECTORY include/ DESTINATION include)
