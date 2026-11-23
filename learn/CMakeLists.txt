# Trainer: pure Python package, tests, the text development client and the
# Cloudflare progress Worker.
#
# Targets:
#   learn-test          run the Python unit tests
#   learn-test-live     run live Worker tests (requires BIRDS_TEST_* env)
#   learn-run           run the interactive text client
#   learn-worker-data   generate the Worker's bundled dataset module
#   learn-worker-test   run the Worker tests with Node's built-in runner
#   learn-worker-dev    run the Worker locally with wrangler
#   learn-worker-deploy deploy the Worker with wrangler

set(LEARN_SRC "${BIRDS_LEARN_SRC}")
set(LEARN_CLOUDFLARE "${BIRDS_ROOT}/learn/cloudflare")

file(GLOB_RECURSE LEARN_PY CONFIGURE_DEPENDS
    "${LEARN_SRC}/trainer/*.py"
    "${LEARN_SRC}/tests/*.py")
file(GLOB_RECURSE LEARN_WORKER CONFIGURE_DEPENDS
    "${LEARN_CLOUDFLARE}/src/*.js"
    "${LEARN_CLOUDFLARE}/tests/*.js")

add_custom_target(learn-worker-data
    COMMAND "${Python3_EXECUTABLE}"
        "${BIRDS_ROOT}/learn/tools/build_worker_data.py"
    DEPENDS
        "${BIRDS_DATA_OUT}/israel_birds_final.json"
        "${BIRDS_DATA_OUT}/etymology.json"
    COMMENT "Generating the Worker dataset module"
    VERBATIM)

find_program(NODE_EXECUTABLE node)

message(STATUS "birds: trainer ${LEARN_SRC}")
if(NODE_EXECUTABLE)
    message(STATUS "birds: node    ${NODE_EXECUTABLE}")
else()
    message(STATUS "birds: node not found; learn-worker-test is unavailable")
endif()

add_custom_target(learn-test
    COMMAND "${Python3_EXECUTABLE}" -m unittest discover -s tests -v
    WORKING_DIRECTORY "${LEARN_SRC}"
    DEPENDS ${LEARN_PY}
    COMMENT "Running trainer tests"
    VERBATIM)

add_custom_target(learn-test-live
    COMMAND "${Python3_EXECUTABLE}" -m unittest -v tests.test_cloud_live
    WORKING_DIRECTORY "${LEARN_SRC}"
    DEPENDS ${LEARN_PY}
    COMMENT "Running live Worker tests (requires BIRDS_TEST_* env)"
    USES_TERMINAL
    VERBATIM)

add_custom_target(learn-run
    COMMAND "${Python3_EXECUTABLE}" -m trainer
    WORKING_DIRECTORY "${LEARN_SRC}"
    DEPENDS ${LEARN_PY}
    COMMENT "Running the trainer text client"
    USES_TERMINAL
    VERBATIM)

if(NODE_EXECUTABLE)
    add_custom_target(learn-worker-test
        COMMAND "${NODE_EXECUTABLE}" --test
        WORKING_DIRECTORY "${LEARN_CLOUDFLARE}"
        DEPENDS ${LEARN_WORKER}
        COMMENT "Running Cloudflare Worker tests"
        VERBATIM)
    add_test(
        NAME learn-worker
        COMMAND "${NODE_EXECUTABLE}" --test
        WORKING_DIRECTORY "${LEARN_CLOUDFLARE}")
    add_dependencies(learn-worker-test learn-worker-data)
else()
    add_custom_target(learn-worker-test
        COMMAND "${CMAKE_COMMAND}" -E echo
            "Node.js is required for learn-worker-test"
        COMMAND "${CMAKE_COMMAND}" -E false
        COMMENT "Node.js not found"
        VERBATIM)
endif()

add_custom_target(learn-worker-dev
    COMMAND npx wrangler dev
    WORKING_DIRECTORY "${LEARN_CLOUDFLARE}"
    COMMENT "Running the progress Worker locally"
    USES_TERMINAL
    VERBATIM)

add_custom_target(learn-worker-deploy
    COMMAND npx wrangler deploy
    WORKING_DIRECTORY "${LEARN_CLOUDFLARE}"
    COMMENT "Deploying the progress Worker"
    USES_TERMINAL
    VERBATIM)

add_dependencies(learn-worker-dev learn-worker-data)
add_dependencies(learn-worker-deploy learn-worker-data)
