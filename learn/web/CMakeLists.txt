# Browser client. Static HTML/CSS/JS staged under build/web; the Worker
# remains the only data path (local or remote by the page's meta tag).
#
# Targets:
#   learn-web-build          stage the client files in build/web
#   learn-web-illustrations        fetch and resize the images into build/media
#   learn-web-illustrations-upload-local upload them to the local R2 emulation
#   learn-web-illustrations-upload-remote upload them to the deployed bucket
#   learn-web-token                mint a local dev token into build/web/dev-login.html
#   learn-web-serve          stage and serve them on http://localhost:8001

set(WEB_SRC "${CMAKE_CURRENT_SOURCE_DIR}")
set(WEB_OUT "${CMAKE_BINARY_DIR}/web")
set(WEB_PORT 8001)
set(BIRDS_DEV_USER "ran" CACHE STRING "Account used by learn-web-token")

file(GLOB_RECURSE WEB_FILES CONFIGURE_DEPENDS
    "${WEB_SRC}/index.html"
    "${WEB_SRC}/src/*.js"
    "${WEB_SRC}/assets/*")

# Remove only the staged client files, so the generated dev-login.html (a
# development credential) survives a restage.
add_custom_target(learn-web-build
    COMMAND "${CMAKE_COMMAND}" -E rm -rf
        "${WEB_OUT}/index.html" "${WEB_OUT}/src" "${WEB_OUT}/assets"
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${WEB_OUT}"
    COMMAND "${CMAKE_COMMAND}" -E copy_directory "${WEB_SRC}" "${WEB_OUT}"
    DEPENDS ${WEB_FILES}
    COMMENT "Staging the browser client in ${WEB_OUT}"
    VERBATIM)

add_custom_target(learn-web-illustrations
    COMMAND "${Python3_EXECUTABLE}"
        "${BIRDS_ROOT}/learn/tools/build_web_illustrations.py"
    DEPENDS
        "${BIRDS_DATA_OUT}/israel_birds_final.json"
        "${WEB_SRC}/illustrations.json"
        "${BIRDS_ROOT}/learn/tools/build_web_illustrations.py"
    COMMENT "Fetching and resizing bird illustrations into build/media"
    USES_TERMINAL
    VERBATIM)

add_custom_target(learn-web-illustrations-upload-local
    COMMAND "${Python3_EXECUTABLE}"
        "${BIRDS_ROOT}/learn/tools/upload_web_illustrations.py" --local
    DEPENDS learn-web-illustrations
    COMMENT "Uploading bird illustrations to the local R2 emulation"
    USES_TERMINAL
    VERBATIM)

add_custom_target(learn-web-illustrations-upload-remote
    COMMAND "${Python3_EXECUTABLE}"
        "${BIRDS_ROOT}/learn/tools/upload_web_illustrations.py" --remote
    DEPENDS learn-web-illustrations
    COMMENT "Uploading bird illustrations to the deployed bucket"
    USES_TERMINAL
    VERBATIM)

add_custom_target(learn-web-token
    COMMAND "${Python3_EXECUTABLE}"
        "${BIRDS_ROOT}/learn/tools/mint_token.py"
        --user "${BIRDS_DEV_USER}"
        --out "${WEB_OUT}/dev-login.html"
        --serve-url "http://localhost:${WEB_PORT}"
    DEPENDS learn-web-build
    COMMENT "Minting a local dev token for ${BIRDS_DEV_USER} (learn-web-token USER=... to override)"
    VERBATIM)

add_custom_target(learn-web-serve
    COMMAND "${Python3_EXECUTABLE}" -m http.server ${WEB_PORT}
        --directory "${WEB_OUT}"
    DEPENDS learn-web-build
    COMMENT "Serving the browser client on http://localhost:${WEB_PORT}"
    USES_TERMINAL
    VERBATIM)
