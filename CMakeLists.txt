cmake_minimum_required(VERSION 3.20)

project(birds VERSION 0.1.0 LANGUAGES NONE)

find_package(Python3 3.11 REQUIRED COMPONENTS Interpreter)

enable_testing()

# Repository layout. All paths are rooted at the repository, not at the
# disposable build tree.
set(BIRDS_ROOT       "${CMAKE_CURRENT_SOURCE_DIR}")
set(BIRDS_BUILD      "${CMAKE_BINARY_DIR}")
set(BIRDS_DATA_IN    "${BIRDS_ROOT}/data/in")
set(BIRDS_DATA_OUT   "${BIRDS_ROOT}/data/out")
set(BIRDS_DATA_SRC   "${BIRDS_ROOT}/data/src")
set(BIRDS_BOOK_SRC   "${BIRDS_ROOT}/book/src")
set(BIRDS_BOOK_DATA  "${BIRDS_ROOT}/book/data")
set(BIRDS_BOOK_OUT   "${BIRDS_ROOT}/book/out"
    CACHE PATH "Installed book output directory")
set(BIRDS_LEARN_SRC  "${BIRDS_ROOT}/learn/src")
set(BIRDS_LEARN_DATA "${BIRDS_ROOT}/learn/data")

message(STATUS "birds: Python       ${Python3_EXECUTABLE}")
message(STATUS "birds: build tree   ${BIRDS_BUILD}")
message(STATUS "birds: data in/out  ${BIRDS_DATA_IN} -> ${BIRDS_DATA_OUT}")
message(STATUS "birds: book out      ${BIRDS_BOOK_OUT}")

# Each project owns its CMakeLists.txt. They are added only when present, so
# this top-level file can be configured and reviewed before the subprojects
# are written.
foreach(subproject data book learn)
    if(EXISTS "${BIRDS_ROOT}/${subproject}/CMakeLists.txt")
        add_subdirectory("${BIRDS_ROOT}/${subproject}"
                         "${BIRDS_BUILD}/${subproject}")
    else()
        message(STATUS
            "birds: ${subproject}/CMakeLists.txt not present yet; skipping")
    endif()
endforeach()

add_custom_target(birds-help
    COMMAND ${CMAKE_COMMAND} -E echo "Configure:  cmake -S . -B build -G Ninja"
    COMMAND ${CMAKE_COMMAND} -E echo "Build all:  cmake --build build"
    COMMAND ${CMAKE_COMMAND} -E echo "Data build:  cmake --build build --target data-build"
    COMMAND ${CMAKE_COMMAND} -E echo "Data install: cmake --build build --target data-install"
    COMMAND ${CMAKE_COMMAND} -E echo "Data test:   cmake --build build --target data-test"
    COMMAND ${CMAKE_COMMAND} -E echo "Book build:  cmake --build build --target book-build"
    COMMAND ${CMAKE_COMMAND} -E echo "Book install: cmake --build build --target book-install"
    COMMAND ${CMAKE_COMMAND} -E echo "Learn run:   cmake --build build --target learn-run"
    COMMAND ${CMAKE_COMMAND} -E echo "Learn test:  cmake --build build --target learn-test"
    COMMAND ${CMAKE_COMMAND} -E echo "Data flow:   cmake --workflow --preset data"
    COMMAND ${CMAKE_COMMAND} -E echo "Book flow:   cmake --workflow --preset book"
    COMMAND ${CMAKE_COMMAND} -E echo "Tests:       ctest --test-dir build"
    VERBATIM)
