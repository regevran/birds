# Data pipeline: data/in -> build/data -> data/out.
#
# Targets:
#   data           build intermediates and final data in build/data
#   install-data   copy the final JSONs to data/out
#   test-data      run the etymology consistency check
#
# The scripts are stdlib-only Python and use
# data/src/pipeline/data_paths.py for every input and output location.

set(DATA_IN       "${BIRDS_DATA_IN}")
set(DATA_OUT      "${BIRDS_DATA_OUT}")
set(DATA_PIPELINE "${BIRDS_DATA_SRC}/pipeline")
set(DATA_BUILD    "${BIRDS_BUILD}/data")

set(RAW_JSON    "${DATA_BUILD}/israel_birds_raw.json")
set(MERGED_JSON "${DATA_BUILD}/israel_birds_merged.json")
set(FINAL_JSON  "${DATA_BUILD}/israel_birds_final.json")
set(ETYM_JSON   "${DATA_BUILD}/etymology.json")

file(MAKE_DIRECTORY "${DATA_BUILD}")

message(STATUS "birds: data pipeline ${DATA_IN} -> ${DATA_BUILD} -> ${DATA_OUT}")

add_custom_command(
    OUTPUT  "${RAW_JSON}"
    COMMAND "${Python3_EXECUTABLE}" "${DATA_PIPELINE}/parse_list.py"
    DEPENDS "${DATA_PIPELINE}/parse_list.py"
            "${DATA_PIPELINE}/data_paths.py"
            "${DATA_IN}/raw/en_israel.wiki"
    COMMENT "Parsing the species list"
    VERBATIM)

add_custom_command(
    OUTPUT  "${MERGED_JSON}"
    COMMAND "${Python3_EXECUTABLE}" "${DATA_PIPELINE}/merge_data.py"
    DEPENDS "${RAW_JSON}"
            "${DATA_PIPELINE}/merge_data.py"
            "${DATA_PIPELINE}/data_paths.py"
            "${DATA_IN}/hebrew_names.json"
    COMMENT "Merging Hebrew names into the species list"
    VERBATIM)

add_custom_command(
    OUTPUT  "${FINAL_JSON}"
    COMMAND "${Python3_EXECUTABLE}" "${DATA_PIPELINE}/build_final.py"
    DEPENDS "${MERGED_JSON}"
            "${DATA_PIPELINE}/build_final.py"
            "${DATA_PIPELINE}/data_paths.py"
            "${DATA_IN}/family_hebrew.json"
    COMMENT "Building the final species dataset"
    VERBATIM)

add_custom_command(
    OUTPUT  "${ETYM_JSON}"
    COMMAND "${Python3_EXECUTABLE}" "${DATA_PIPELINE}/build_etymology.py"
    DEPENDS "${FINAL_JSON}"
            "${DATA_PIPELINE}/build_etymology.py"
            "${DATA_PIPELINE}/data_paths.py"
            "${DATA_IN}/etymology.md"
    COMMENT "Building the etymology dataset"
    VERBATIM)

add_custom_target(data ALL
    DEPENDS "${RAW_JSON}" "${MERGED_JSON}" "${FINAL_JSON}" "${ETYM_JSON}")

# The final JSON includes `family_order` (1..84, by first appearance in the
# source checklist). The book still reads build/data/israel_birds_merged.json
# for family order; switching it to `family_order` is a book TODO.

add_custom_target(install-data
    COMMAND "${CMAKE_COMMAND}" -E make_directory "${DATA_OUT}"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${FINAL_JSON}" "${DATA_OUT}/israel_birds_final.json"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${ETYM_JSON}" "${DATA_OUT}/etymology.json"
    DEPENDS "${FINAL_JSON}" "${ETYM_JSON}"
    COMMENT "Installing final data into data/out"
    VERBATIM)

add_custom_target(test-data
    COMMAND "${Python3_EXECUTABLE}" "${DATA_PIPELINE}/build_etymology.py" --check
    DEPENDS "${FINAL_JSON}"
            "${DATA_PIPELINE}/build_etymology.py"
            "${DATA_PIPELINE}/data_paths.py"
            "${DATA_IN}/etymology.md"
    COMMENT "Validating etymology data"
    VERBATIM)
