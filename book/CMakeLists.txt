# A5 book: book/data + data/out -> build/book -> book/out.
#
# Targets:
#   book-build     build the interior, cover PDFs and full one-file book
#   book-one-file  build only the combined front-cover + interior + back-cover PDF
#   book-install   copy all print PDFs to book/out
#
# The builders are Python/reportlab scripts; data/out is the installed data
# contract. The cover reads the interior's page count, so it is built after
# the interior.

set(BOOK_SRC   "${BIRDS_BOOK_SRC}")
set(BOOK_DATA  "${BIRDS_BOOK_DATA}")
set(BOOK_BUILD "${BIRDS_BUILD}/book")
set(BOOK_OUT   "${BIRDS_BOOK_OUT}")

set(POCKET_PDF      "${BOOK_BUILD}/israel_birds_pocket.pdf")
set(COVER_PDF       "${BOOK_BUILD}/cover_spread.pdf")
set(COVER_FRONT_PDF "${BOOK_BUILD}/cover_front_print.pdf")
set(COVER_BACK_PDF  "${BOOK_BUILD}/cover_back_print.pdf")
set(COVER_FRONT_TRIM "${BOOK_BUILD}/cover_front.pdf")
set(COVER_BACK_TRIM  "${BOOK_BUILD}/cover_back.pdf")
set(ONE_FILE_PDF     "${BOOK_BUILD}/israel_birds_one_file.pdf")

file(MAKE_DIRECTORY "${BOOK_BUILD}")

message(STATUS "birds: book ${BOOK_DATA} + ${BIRDS_DATA_OUT} -> "
               "${BOOK_BUILD} -> ${BOOK_OUT}")

set(BOOK_PY
    "${BOOK_SRC}/book_paths.py"
    "${BOOK_SRC}/book_text.py"
    "${BOOK_SRC}/etym.py"
    "${BOOK_SRC}/make_book.py"
    "${BOOK_SRC}/make_book_family.py"
    "${BOOK_SRC}/mixed_text.py"
    "${BOOK_SRC}/pocket_fonts.py")

set(BOOK_DATA_FILES
    "${BOOK_DATA}/text.md"
    "${BOOK_DATA}/assets/logo_circle.png"
    "${BOOK_DATA}/assets/logo_circle_gray.png")

set(BOOK_DATA_INPUTS
    "${BIRDS_DATA_OUT}/israel_birds_final.json"
    "${BIRDS_DATA_OUT}/etymology.json")

add_custom_command(
    OUTPUT  "${POCKET_PDF}"
    COMMAND "${Python3_EXECUTABLE}" "${BOOK_SRC}/make_pocket.py"
            --out "${POCKET_PDF}"
    DEPENDS "${BOOK_SRC}/make_pocket.py"
            ${BOOK_PY}
            ${BOOK_DATA_FILES}
            ${BOOK_DATA_INPUTS}
    COMMENT "Building the A5 interior"
    VERBATIM)

# --panels writes the A5 trim cover panels for the one-file sequence;
# --split writes the two 154 x 216 mm print panels; both share the spread.
add_custom_command(
    OUTPUT  "${COVER_PDF}" "${COVER_FRONT_PDF}" "${COVER_BACK_PDF}"
            "${COVER_FRONT_TRIM}" "${COVER_BACK_TRIM}"
    COMMAND "${Python3_EXECUTABLE}" "${BOOK_SRC}/make_cover.py"
            --out "${BOOK_BUILD}" --panels --split
    DEPENDS "${POCKET_PDF}"
            "${BOOK_SRC}/make_cover.py"
            ${BOOK_PY}
            ${BOOK_DATA_FILES}
            ${BOOK_DATA_INPUTS}
    COMMENT "Building the colour cover"
    VERBATIM)

find_program(PDFUNITE_EXECUTABLE pdfunite REQUIRED)

add_custom_command(
    OUTPUT  "${ONE_FILE_PDF}"
    COMMAND "${PDFUNITE_EXECUTABLE}"
            "${COVER_FRONT_TRIM}" "${POCKET_PDF}" "${COVER_BACK_TRIM}"
            "${ONE_FILE_PDF}"
    DEPENDS "${COVER_FRONT_TRIM}" "${POCKET_PDF}" "${COVER_BACK_TRIM}"
    COMMENT "Building the one-file book"
    VERBATIM)

add_custom_target(book-one-file
    DEPENDS "${ONE_FILE_PDF}")

add_custom_target(book-build ALL
    DEPENDS "${POCKET_PDF}" "${COVER_PDF}"
            "${COVER_FRONT_PDF}" "${COVER_BACK_PDF}"
            "${COVER_FRONT_TRIM}" "${COVER_BACK_TRIM}"
            "${ONE_FILE_PDF}")

add_custom_target(book-install
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${BOOK_OUT}"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${POCKET_PDF}" "${BOOK_OUT}/israel_birds_pocket.pdf"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${COVER_PDF}" "${BOOK_OUT}/cover_spread.pdf"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${COVER_FRONT_PDF}" "${BOOK_OUT}/cover_front_print.pdf"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${COVER_BACK_PDF}" "${BOOK_OUT}/cover_back_print.pdf"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${ONE_FILE_PDF}" "${BOOK_OUT}/israel_birds_one_file.pdf"
    DEPENDS "${POCKET_PDF}" "${COVER_PDF}"
            "${COVER_FRONT_PDF}" "${COVER_BACK_PDF}"
            "${ONE_FILE_PDF}"
    COMMENT "Installing book PDFs into book/out"
    VERBATIM)
