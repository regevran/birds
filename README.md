# Birds of Israel — A5 pocket edition

An A5 perfect-bound pocket book of Israel's birds: a Hebrew interior with
Latin, English and Hebrew names, etymology indexes, and a colour cover.

## Directory

- `book/` — the A5 builders, `text.md`, fonts, assets and print notes.
- `data/` — species, Hebrew/English names, etymologies and source family order.
- `tools/` — shared data-building scripts and the older A4 layout code.
- `out/` — generated PDFs: interior, cover and index previews.

The entry point is `render.sh`; design decisions and the current index plan
are in `REFERENCE.md`.

## Generate the book

One-time setup:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install reportlab python-bidi fonttools
```

Build the interior and cover:

```sh
./render.sh
```

Build one file for the copy shop — front cover, interior, back cover:

```sh
./render.sh --one-file
```

Outputs land in `out/book/`:

- `israel_birds_pocket.pdf` — interior
- `cover_spread.pdf` — cover with bleed
- `israel_birds_one_file.pdf` — the one-file sequence

`--one-file` needs `pdfunite` (Poppler); the cover build uses `pdfinfo`.
See `book/PRINT.md` for the full print brief and `book/README.md` for the
inspector-level build notes.

Index proofs, with their final folios in the new structure:

```sh
python3 book/make_pocket.py --preview-themes
python3 book/make_pocket.py --preview-themes-hebrew
python3 book/make_pocket.py --preview-key
python3 book/make_pocket.py --preview-hebrew
python3 book/make_pocket.py --preview-english
python3 book/make_pocket.py --preview-families
python3 book/make_pocket.py --preview-latin-species
python3 book/make_pocket.py --preview-elements
```
