cmake_minimum_required (VERSION 3.7)

project(mnoda CXX)

set (ENABLE_GMOCK ON CACHE PATH "")

set(CMAKE_CXX_FLAGS ${MNODA_BASE_CXX_FLAGS})
include(blt/SetupBLT.cmake)

# Now that BLT has built gtest and gmock, we can use our own flags for our
# main code. If we do this too early, the gtest/gmock builds will fail
set(CMAKE_CXX_FLAGS ${MNODA_CXX_FLAGS})

include_directories("${PROJECT_SOURCE_DIR}/include")

install(DIRECTORY "include/mnoda"
    DESTINATION "include")

add_subdirectory(src)
add_subdirectory(test)
add_subdirectory(docs)
