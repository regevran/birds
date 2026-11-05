"""Filesystem layout for the book project.

Keep path changes here so a future repository move is a one-file change.
The repository root is resolved from this file's location:
``book/src/book_paths.py`` -> ``book/src`` -> ``book`` -> repository.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOK_ROOT = REPO_ROOT / "book"
BOOK_SRC = BOOK_ROOT / "src"
BOOK_DATA = BOOK_ROOT / "data"
BOOK_OUT = BOOK_ROOT / "out"

BUILD_ROOT = REPO_ROOT / "build"
BUILD_BOOK = BUILD_ROOT / "book"
BUILD_DATA = BUILD_ROOT / "data"

DATA_IN = REPO_ROOT / "data" / "in"
DATA_OUT = REPO_ROOT / "data" / "out"

TEXT = str(BOOK_DATA / "text.md")
ASSETS = str(BOOK_DATA / "assets")
LOGO_COVER = str(BOOK_DATA / "assets" / "logo_circle.png")
LOGO_GRAY = str(BOOK_DATA / "assets" / "logo_circle_gray.png")

SPECIES = str(DATA_OUT / "israel_birds_final.json")
ETYMOLOGY = str(DATA_OUT / "etymology.json")
ORDER_SOURCE = str(BUILD_DATA / "israel_birds_merged.json")

OUT_DIR = str(BUILD_BOOK)
INSTALL_DIR = str(BOOK_OUT)
DEFAULT_POCKET = str(BUILD_BOOK / "israel_birds_pocket.pdf")
DEFAULT_A4 = str(BUILD_BOOK / "israel_birds.pdf")
DEFAULT_FAMILY = str(BUILD_BOOK / "israel_birds_by_family.pdf")
DEFAULT_DEMO = str(BUILD_BOOK / "etymology_layout_demo.pdf")
