# Book reference

Read before changing the A5 book. Repository layout and general build commands
are in `repository.md`; this file covers the book itself.

## Status

- First edition: 72 pages, perfect bound, A5 148 × 210 mm; five copies printed.
- Second edition: 96-page design; its on-paper lessons are folded into
  **Lessons** below.
- Current third edition (2026): 96 pages, same structure, rebuilt cover for a
  5.28 mm spine. Interior is **K-only** (C=M=Y=0); the logo is grayscale. The
  cover is full colour. The cover reads the interior page count and derives
  the spine.

## Structure

- Front matter: five pages — title (unnumbered), copyright ii, dedication iii,
  contents iv, key v.
- Themed word-element data: Arabic 1–7, one column; content, not an index.
  Title: `מרכיבי השמות לפי קבוצות`.
- Species list: 8–53.
- Indexes: see below.
- Whole names: 75.
- Notes: 86–87, then two blank note pages and padding to 96.

```text
front matter          5
themed elements       7
species list         46   -> 8–53
Hebrew species        5   -> 54–58
English species       7   -> 59–65
Latin families        1   -> 66
Hebrew families       1   -> 67
Latin species         7   -> 68–74
whole names           1   -> 75
word elements        10   -> 76–85
notes                 2   -> 86–87
blank notes           2   -> 88–89
padding               2   -> 90–91
total                     -> 96 pages
```

The sheet count must be a multiple of four. At 90 gsm the spine is
`(pages / 2) × 0.11 mm`; 96 pages give 5.28 mm.

## Files

- `book/src/make_pocket.py` — A5 interior builder.
- `book/src/make_cover.py` — colour cover and spine.
- `book/src/book_paths.py` — central paths.
- `book/src/book_text.py` — parser for `text.md`.
- `book/src/mixed_text.py` — mixed Hebrew/Latin bidi and font runs.
- `book/src/pocket_fonts.py` — font registration.
- `book/src/etym.py` — etymology splits, glossary/index data and colours.
- `book/src/make_book.py`, `book/src/make_book_family.py` — shared layout
  helpers.
- `book/data/text.md` — all printed prose; edit here, not in the builders.
- `data/out/israel_birds_final.json`, `data/out/etymology.json` — installed
  data inputs.
- `book/CMakeLists.txt` — `book-build`, `book-one-file`, `book-install`.
- `book/PRINT.md`, `book/README.md` — print brief and detailed notes.

The build reads only `data/out` and sorts families by `family_order`; it does
not read the merged build intermediate.

## Build

System `python3` lacks the render dependencies; use a venv:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install reportlab python-bidi fonttools
```

```sh
cmake --workflow --preset book
```

Targets and the general build command list are in `repository.md`
(`book-build`, `book-one-file`, `book-install`). Preview individual sections
with final folios (proofs only):

```sh
python3 book/src/make_pocket.py --preview-themes
python3 book/src/make_pocket.py --preview-themes-hebrew
python3 book/src/make_pocket.py --preview-key
python3 book/src/make_pocket.py --preview-hebrew
python3 book/src/make_pocket.py --preview-hebrew --hebrew-columns 2
python3 book/src/make_pocket.py --preview-english
python3 book/src/make_pocket.py --preview-families
python3 book/src/make_pocket.py --preview-latin-species
python3 book/src/make_pocket.py --preview-elements
```

`pdfinfo`/`pdfunite` come from Poppler; `gs -sDEVICE=inkcov` checks K-only
interiors.

## Cover

- Hebrew and Latin only; English appears only as bird names and element
  glosses. Author in Hebrew on the front; back cover in Hebrew and Latin.
- Sand field, ochre accent, dark ink; no decorative stripes (they looked like
  cutting marks).
- The cover reads the interior page count and computes the spine; rebuild
  after the interior is final.
- `--split` writes `cover_front_print.pdf` and `cover_back_print.pdf`
  (154 × 216 mm, 3 mm bleed, no spine band); the spread remains primary.

## Index system

| Index | Marker | Cols | Type | Pages |
|---|---|---|---|---|
| Hebrew species | α | 3 | Hebrew names + refs | 54–58 |
| English species | η | 2 | English names + refs | 59–65 |
| Latin families | φ | 3 | Latin family + refs | 66 |
| Hebrew families | μ | 3 | Hebrew family + refs | 67 |
| Latin species | λ | 2 | Latin binomial + refs | 68–74 |
| Whole names | σ | 1 | whole name + gloss + refs | 75 |
| Word elements | ρ | 1 | element + pages + Hebrew + group + refs | 76–85 |

- Latin-script indexes (English, Latin families, Latin species, whole names,
  word elements) are assigned pages in reverse so a physical left-to-right
  scan reads A–Z. Hebrew indexes keep right-to-left order.
- μ is provisional (mnemonic *mishpacha*) and easy to change.
- English and Latin-species indexes use two columns because long names do not
  fit three (longest ~54 mm and ~56 mm at 8 pt).
- Latin and Hebrew family indexes are deliberately separate; together a row
  needed two columns, separately each fits three on one page.
- Name and element indexes are pure (name + page refs). The whole-name index
  is the one exception: a small glossary with gloss and source.
- References point to the first page of a species/family in the list (8–53).
- Letter headings repeat atop each column/page; the box shows first and last
  letter.
- Word-element rows: **glossary page first, then occurrence pages in
  parentheses**. The fixed row is Latin element (hanging leading hyphen) ·
  themed page · Hebrew meaning · short group label · occurrence pages.
  Consecutive pages compress to ranges. Column titles: `מרכיב · עמוד · משמעות ·
  קבוצה · עמודי רשימה`.
- The element list normally runs 7.8 pt; only the longest lists shrink
  (≈5.5–6.7 pt) so the fixed column never breaks.
- The themed pages use the title `מרכיבי השמות לפי קבוצות` (not “מפתח”).
  Group headings are 15 pt bold with a rule. Entries sort by Hebrew meaning
  and merge: one line carries every Latin form sharing that meaning, plus the
  English gloss and the Hebrew meaning once. Long form lines shrink to stay on
  one line; the longest (nine forms, bill) is ~5.6 pt. This yields 7 pages.

## How to read this book

The key page (v) has four blocks: `סדר`, `סימונים`, `סימוני מינים`, `מפתחות`.
It carries the index order, the data-versus-index distinction, the grouped
Latin forms, the seven mnemonics (אלפא, אתא, פי, מו, למבדא, סיגמא, רו) with the
matching initial bolded, and the margin-tag explanation. `רשימת חלופות`
explains that each themed line gathers all forms of one Hebrew meaning;
`סימונים` explains the asterisk after a whole name. The old taxonomic note was
condensed into the opening section; the Clements source remains on the
copyright page.

## Index markers

- One box per index: **19 mm × 4.2 mm**, outer fore-edge, 5 mm inside trim —
  left on versos, right on rectos.
- One **20 mm slot** per index, α at the top and each following marker 20 mm
  lower; seven fit in 140 mm.
- Box contents: Greek letter, a small gap, then the page's first and last
  letter (once if only one). Fixed size; no next-letter line.
- These are printed margin markers for riffling, not cut thumb tabs. No
  continuation notation for now.

## Typography and geometry

- Base text 10 pt; A5 148 × 210 mm; text width 122 mm (13 mm sides, 14 mm top,
  15 mm bottom).
- Latin: Noto Sans Mono (`BirdLatin`, `BirdLatinBold`).
- Hebrew: Droid Sans Hebrew (`BirdHebrew`, `BirdHebrewBold`); it lacks ASCII
  punctuation/digits/Latin, so mixed text uses font runs.
- Three-column indexes: 5 mm gutters, 37.3 mm columns. Two-column: 6 mm
  gutter, 58 mm columns.
- Index sizes: Hebrew species 8.8/7.8; English 8.0/7.2; Latin families
  8.2/7.4; Hebrew families 8.8/7.8. Letter headings 15 pt.
- K-only: K100 body, K75 secondary, K70 etymology, K60 labels, K35–K55 rules.

## Editing rules

- All printed prose is in `book/data/text.md`; the parser fails on missing or
  duplicate keys.
- Hebrew values may contain ASCII punctuation, digits and Latin; the renderer
  splits font runs.
- Use maqaf (`־`) and geresh/gershayim (`׳`/`״`) inside Hebrew.
- A block line ending in `\` forces a hard break. `כותרת: X` starts a section
  title; `- ` starts a bullet; the markers are not printed. `#` lines are
  notes, not printed.

## Lessons

- Indexes must be alphabetical and pure; the themed element list is content
  and stays separate.
- A whole name that is exactly an element form (`alba`, `Anser`) is still a
  split and is set grey. The source keeps only forms that occur in a name; the
  build rejects unused forms and `Etymology.form_rows()` filters as a guard.
- Do not paginate one letter per page; let large letters split.
- Keep family indexes separate so both fit three columns.
- Print edge tabs on the outer edge; reverse Latin-script index pages so a
  left-to-right scan reads A–Z.
- Show full absolute paths to proof PDFs, not relative paths.
- Keep the key page and the index table in this file in step.
- Second-edition corrections, now fixed: `hispaniol` = Spain/ספרד; `rubi-` =
  bramble-bush under “Where it lives” (Jobling confirms).

## Next work

Read the assembled interior and cover proofs end to end, checking alternating
edge tabs and the left-to-right Latin/English indexes.

## Don't

- Don't commit unless asked.
- Don't rebuild/print the cover while the page count is moving.
- Don't mix index data into another index.
- Don't add explanatory subtitles to self-evident indexes.
