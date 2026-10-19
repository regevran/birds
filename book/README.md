# Birds of Israel — A5 pocket edition

A separate work from the A4 learning sheets.  It reuses the same source data but
has its own layout, front matter, colour, indexes and cover.  Nothing in
`tools/` or `data/` is modified by the build; only `book/` and `out/book/` are.

## Build

```sh
./render.sh
```

`render.sh` builds the interior and then the cover, in that order; the cover
reads the interior's page count to compute the spine. Use `--interior-only` or
`--cover-only` to run just one half, and see `./render.sh --help` for the
builder options (`--base`, `--pages`, `--caliper`, `--spine`).

Outputs:

| File | What it is |
|---|---|
| `out/book/israel_birds_pocket.pdf` | interior, A5, 72 pages, numbered from the first list page |
| `out/book/cover_spread.pdf` | back + spine + front, spine computed from the interior |

The front panel alone is a proof, not a build artifact: write it on demand
with `python3 book/make_cover.py --front-only` (it lands in
`out/book/cover_front_draft.pdf`, 154 × 216 mm).

The cover script reads the interior's page count with `pdfinfo`, so rebuilding
after a content change keeps the spine correct.

## Editing the text

All printed prose lives in **`book/text.md`** — title, dedication, copyright,
contents labels, the “How to use this book” page, index headings, the notes
page, and the cover text. Edit that file and rebuild; neither `make_pocket.py`
nor `make_cover.py` contains prose any more.

Format:

- `## section` groups keys by where they appear; the section comments say
  which page or cover panel they belong to.
- `key: value` is a single line.
- `key: |` followed by four-space-indented lines is a paragraph; the lines are
  joined with spaces and wrapped by the layout, so you can break them wherever
  is comfortable.
- Lines beginning with `#` are notes and are not printed.

Two cautions: Hebrew values should use Hebrew letters, spaces and the maqaf
(־) — the Hebrew font does not carry ASCII punctuation; and the cover birds and
word elements are drawn from the species and etymology data, so their names and
meanings are not in the text file. `book/book_text.py` is the small parser; it
fails loudly on a missing or duplicated key.

Data — species, names, etymologies and order names — stays in `data/`.

## What is in the book

- **Front matter, unnumbered:** title, copyright, dedication, contents, key.
  The dedication is the two lines `לשאול,` /
  `שבכלל לא צריך את הספר הזה.` at the top right.
- **The list, pages 1–46:** 565 species in 84 families. **Families are in
  taxonomic order** (Clements 2022), with a heading for each of the 26 orders;
  genera and species are alphabetical inside a family. Latin on the left,
  **English in a fixed middle column**, Hebrew on the right; markers (`A`, `I`,
  `Ex`, `X`) in parentheses at the end of the Hebrew name; etymology split in
  grey with a raised dot.
- **Hebrew name index, pages 47–54:** 559 names in Hebrew dictionary order,
  two columns flowing right-to-left, page references to the list. It comes
  before the word-element index because it is the faster way into the book.
- **Index of word elements, pages 55–65:** the 380 surface forms, one column,
  themed and alphabetical, with element · English · Hebrew.
- **Notes, page 66**, followed by blanks to a multiple of four pages.

## Design decisions

- **A5 (148 × 210 mm), one text column, 10 pt.** One A5 page is about one column
  of the old A4 two-column sheets, so the type size carries over unchanged.
- **Two orders, on purpose.** The list follows the taxonomic sequence of the
  Clements Checklist (2022), so related families sit together and the order
  carries information. The contents, the Hebrew name index and the element
  index are alphabetical, because a printed book is faster to search by name.
  The key page carries a short note explaining this division; the copyright
  page names the sequence source.
- **Three fields per row.** Latin, English, Hebrew. English starts at a fixed
  52 mm column, so every English name lines up down the page. A Latin name that
  would cross that column shrinks on its own row (most names stay at 10 pt);
  English is 70% of the base size in a quieter ink, and Hebrew is 98%. Markers
  hang in parentheses to the left of the Hebrew name, so every Hebrew name
  aligns on the same right edge — the same idea as the dash gutter in the
  element index.
- **Perfect-bound softcover.** 72 pages on 90 gsm paper gives a 3.96 mm spine;
  the spread is 305.96 × 216 mm including 3 mm bleed.
- **Warm palette.** Sand field, ochre accent `#7A4E12` derived from the cover
  mark, dark ink `#2F2714`.  Accent is used for family headings, rules, index
  headings and folios only; the etymology grey `#5A5A5A` stays distinct.
- **Hebrew index order.** Sorted word by word, letters only, final forms filed
  with their regular letters (`ך` as `כ`, etc.).  Columns read right to left:
  the first half of the alphabet is the right-hand column.
- **Cover.** The 13 bands stand for the 13 etymology themes; the mark is the
  *צרים על ציפורים* robin. The examples sit in a light cream frame with an
  ochre border on both panels: the front frame holds the compact European robin
  and its word elements; the back frame holds the Namaqua dove and Eurasian
  nightjar, with the word elements of both. All example information — family,
  names, elements — is inside the frame. Each bird uses the book's own order —
  family, then Latin / English / Hebrew — and the word elements form a separate
  left-aligned list inside the frame, not columns under the bird. There are no
  invented equals signs.

## Printing notes

`book/PRINT.md` is the full brief to send with the files. In short:

- 72 pages, A5, perfect bound, spine 3.96 mm at 90 gsm (0.11 mm/sheet).
- Interior: 90 gsm uncoated, cream/ivory or white, duplex.
- Cover: 250 gsm white matte/silk, matte lamination outside; 3 mm bleed.
- The cover sheet is 305.96 × 216 mm and needs SRA3 or larger (A3 is too
  narrow). Print at 100%, do not mirror.
- The PDFs are RGB. Convert to CMYK if required, and proof: the sand/ochre and
  the interior accent shift most.
- If the paper changes, regenerate the cover rather than scaling it:

  ```sh
  python3 book/make_cover.py --pages 72 --caliper 0.12   # 100 gsm
  python3 book/make_cover.py --pages 72 --spine 4.2      # bindery's final spine
  ```

- Fonts: Noto Sans Mono (Latin) and Droid Sans Hebrew, both subset-embedded.

## Credits and text

The title page, copyright page and cover read their text from `book/text.md`.
The cover birds are selected in `make_cover.py` and drawn from
`data/israel_birds_final.json` and `data/etymology.json`; change the Latin names
there to change an example.

- © 2026 Ran Regev
- Logo: Noa Shvartsun Regev
- Etymologies after James A. Jobling, *Helm Dictionary of Scientific Bird Names*
  (2010); species list and Hebrew names from publicly available sources
  including the English and Hebrew Wikipedias.
- Sequence of orders and families after the *Clements Checklist of Birds of the
  World*, 2022 edition, as presented in the Wikipedia list of birds of Israel.
  The source order is read from `data/israel_birds_merged.json`.
