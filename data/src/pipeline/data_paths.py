"""Filesystem layout for the default data pipeline.

Keep path changes here so a future repository move is a one-file change.
The repository root is resolved from this file's location:
``data/src/pipeline/data_paths.py`` -> ``pipeline`` -> ``src`` -> ``data`` ->
repository.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = REPO_ROOT / "data"
DATA_IN = DATA_ROOT / "in"
DATA_OUT = DATA_ROOT / "out"
BUILD_DATA = REPO_ROOT / "build" / "data"

# The pipeline writes intermediates here; make sure the directory exists.
BUILD_DATA.mkdir(parents=True, exist_ok=True)

RAW_WIKI = str(DATA_IN / "raw" / "en_israel.wiki")
RAW_HTML = str(DATA_IN / "raw" / "en_israel.html")
HEBREW_NAMES = str(DATA_IN / "hebrew_names.json")
HEBREW_WIKIDATA = str(DATA_IN / "hebrew_wikidata.json")
FAMILY_HEBREW = str(DATA_IN / "family_hebrew.json")
ETYMOLOGY_MD = str(DATA_IN / "etymology.md")

BIRDS_RAW = str(BUILD_DATA / "israel_birds_raw.json")
BIRDS_MERGED = str(BUILD_DATA / "israel_birds_merged.json")
BIRDS_FINAL = str(BUILD_DATA / "israel_birds_final.json")
ETYMOLOGY_JSON = str(BUILD_DATA / "etymology.json")

INSTALL_SPECIES = str(DATA_OUT / "israel_birds_final.json")
INSTALL_ETYMOLOGY = str(DATA_OUT / "etymology.json")
