# Trainer: pure Python package, tests and the text development client.
#
# Targets:
#   learn-test   run the unit tests
#   learn-run    run the interactive text client

set(LEARN_SRC "${BIRDS_LEARN_SRC}")

file(GLOB_RECURSE LEARN_PY CONFIGURE_DEPENDS
    "${LEARN_SRC}/trainer/*.py"
    "${LEARN_SRC}/tests/*.py")

message(STATUS "birds: trainer ${LEARN_SRC}")

add_custom_target(learn-test
    COMMAND "${Python3_EXECUTABLE}" -m unittest discover -s tests -v
    WORKING_DIRECTORY "${LEARN_SRC}"
    DEPENDS ${LEARN_PY}
    COMMENT "Running trainer tests"
    VERBATIM)

add_custom_target(learn-run
    COMMAND "${Python3_EXECUTABLE}" -m trainer
    WORKING_DIRECTORY "${LEARN_SRC}"
    DEPENDS ${LEARN_PY}
    COMMENT "Running the trainer text client"
    USES_TERMINAL
    VERBATIM)
