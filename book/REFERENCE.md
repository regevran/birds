# Birds of Israel — working reference

Orientation notes for future sessions. Read this before changing the A5 book.

> **Book work resumed.** The installed `data/out` contract is now the only data
> input; corrections from the printed second edition are recorded at the end
> of this file.

## Repository move

The repository was restructured on 2026-11-05 into:

- `data/src` (pipeline scripts), `data/in` (sources and frozen snapshots),
  `data/out` (installed final data, committed);
- `book/src`, `book/data`, `book/out`;
- `learn/src`, `learn/data`;
- one disposable top-level `build/` for all build artifacts;
- top-level `CMakeLists.txt` and `CMakePresets.json`; `data/CMakeLists.txt`
  and `book/CMakeLists.txt` are written. The `learn` per-project CMake file is
  not present in this checkout.

The book's Python path layer and the default data pipeline's path layer have
been prepared for the move; the one-off data scripts are still untouched. The
book build reads only `data/out` and uses `family_order`. `book/CMakeLists.txt`
provides `book-build`, `book-one-file` and `book-install`; the CMake path is
the supported build, including the combined one-file PDF.

- `book/src/book_paths.py` centralizes the repository root, `book/data`,
  `book/out`, `build/book`, `build/data`, `data/in`, `data/out`, the text and
  asset paths, and the species/etymology files.
- `book/src/make_pocket.py`, `book/src/make_cover.py`,
  `book/src/make_book.py`, `book/src/make_book_family.py`, `book/src/etym.py`
  and `book/src/etymology_demo.py` now use `book_paths`. The stale `ROOT` and
  `tools/` path insert were removed from the two current A5 builders.
- CMake is the only supported build path; `book/README.md` and
  `book/PRINT.md` use the current paths.
- Default pipeline scripts moved to `data/src/pipeline` and now use
  `data/src/pipeline/data_paths.py`:
  - `parse_list.py`: `data/in/raw/en_israel.wiki` ->
    `build/data/israel_birds_raw.json`.
  - `merge_data.py`: `build/data/israel_birds_raw.json` +
    `data/in/hebrew_names.json` -> `build/data/israel_birds_merged.json`.
  - `build_final.py`: `build/data/israel_birds_merged.json` +
    `data/in/family_hebrew.json` -> `build/data/israel_birds_final.json`.
  - `build_etymology.py`: `data/in/etymology.md` +
    `build/data/israel_birds_final.json` -> `build/data/etymology.json`.
  - `data/CMakeLists.txt` defines `data-build`, `data-install` and `data-test`;
    `data-install` copies the final JSONs to `data/out`.
- The data pipeline has been run successfully against the new `data_paths.py`;
  the target is now `data-build`.
- The one-off scripts in `data/src/oneoff` still assume the repository root
  and use old `data/...` paths. They are not part of the default build.
- `data/out/israel_birds_final.json` includes one integer `family_order` per
  species (1..84, by first appearance in the source checklist).
  `make_pocket.py` now sorts families by `family_order` and reads only
  `data/out`; it does not need the merged build intermediate.
- `data/in/overrides/family_hebrew_fixed.json` is a candidate override, not
  wired into the build. Decide whether to apply or delete it.
- `book/data/reports/etymology_mismatches.md` and
  `book/data/assets/source/closing_on_birds_logo.png` are book-specific
  sources/reports moved out of `data/`.
- `data/in/raw/he_israel.html` and `data/in/jobling/jobling_djvu.txt` are
  source snapshots but are not read by any current script.
- `data/out` is committed; `build/` is ignored; `book/out/` is ignored.
- The old A4 PDFs are in `book/out/legacy/`; the A5 outputs in `book/out/`.
- `book/.PRINT.md.swp` is an ignored editor swap file; remove it when
  convenient.
- `learn/` is now `learn/src` + `learn/data/progress`; there is no
  `learn/build` or `learn/out`. `learn/IMPLEMENTATION.md` was updated to the
  new paths.

The build commands below use the moved paths. `book-build` writes to
`build/book/`; `book-install` copies the print PDFs to `book/out/`.

## Status

- The first printed edition was 72 pages, perfect bound, A5 148 × 210 mm;
  five copies were printed.
- The second printed edition was the 96-page design; its on-paper lessons are
  recorded at the end of this file.
- The current third edition keeps the 96-page structure: front matter, themed
  elements, species list, seven indexes, two notes pages and four blanks. The
  cover has been rebuilt for the 5.28 mm spine.
- The interior is **K-only** (C=M=Y=0) and the logo is grayscale. The cover is
  full colour; colour inside was too expensive.
- The cover reads the interior's page count and derives the spine.

## Directory map

- `book/src/make_pocket.py` — the A5 interior builder.
- `book/src/make_cover.py` — the colour cover and spine.
- `book/data/text.md` — all printed prose; edit here, not in the builders.
- `book/src/book_paths.py` — central path definitions for the book.
- `book/src/book_text.py` — parser for `text.md` (`key: value`, `key: |`, `\`
  hard break).
- `book/src/mixed_text.py` — mixed Hebrew/Latin bidi and font-run rendering.
- `book/src/pocket_fonts.py` — font registration.
- `book/src/etym.py` — etymology splits, glossary/index data and colours.
- `book/src/make_book.py`, `book/src/make_book_family.py` — shared Latin/Hebrew
  width and family layout helpers.
- `data/out/israel_birds_final.json` — species rows (installed data).
- `data/out/etymology.json` — element meanings, splits and themes (installed
  data).
- `build/data/israel_birds_merged.json` — build intermediate with the source
  order; the book no longer reads it.
- `book/CMakeLists.txt` — `book-build` (interior, spread, split panels and
  one-file book in `build/book`), `book-one-file` (just the combined PDF) and
  `book-install` (copy all print PDFs to `book/out`).
- `book/PRINT.md` — print brief for the copy shop.
- `book/README.md` — detailed build/edit notes for the A5 edition.

## Build

System `python3` in this environment does not have the render dependencies.
Use a venv:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install reportlab python-bidi fonttools
```

Build and install with CMake:

```sh
cmake --preset default
cmake --build build --target book-build     # -> build/book
cmake --build build --target book-one-file  # just the combined book
cmake --build build --target book-install   # -> book/out
# or: cmake --workflow --preset book
```

Preview the new indexes with their final folios (these do not touch the
assembled interior):

```sh
python3 book/src/make_pocket.py --preview-themes      # themed data, 1–7
python3 book/src/make_pocket.py --preview-themes-hebrew  # Hebrew-sorted output
python3 book/src/make_pocket.py --preview-key         # “How to read this book”
python3 book/src/make_pocket.py --preview-hebrew      # 3 columns, 54–58
python3 book/src/make_pocket.py --preview-hebrew --hebrew-columns 2
python3 book/src/make_pocket.py --preview-english     # 2 columns, 59–65
python3 book/src/make_pocket.py --preview-families    # Latin 66, Hebrew 67
python3 book/src/make_pocket.py --preview-latin-species  # 2 columns, 68–74
python3 book/src/make_pocket.py --preview-elements    # 1 column, 76–85
```

`pdfinfo`/`pdfunite` come from Poppler. `gs -sDEVICE=inkcov` is used to check
that interior pages stay K-only.

Build outputs are in `build/book/`. Previews are proofs, not print files.

## Book structure (assembled)

- Front matter: five pages (title unnumbered; copyright ii, dedication iii,
  contents iv, key v).
- Themed word-element data: Arabic **1–7**, one column; this is content, not
  an index. Its title is `מרכיבי השמות לפי קבוצות`.
- Species list: Arabic **8–53**.
- Indexes: Arabic, in the order below.
- Whole names: page 75.
- Notes: pages 86–87, then two blank note pages and printer padding to 96.
- Themes are sorted by Hebrew meaning; each line merges every Latin form that
  shares one Hebrew meaning. The `--preview-themes-hebrew` output is the same
  setting as the book.

Page arithmetic:

```text
front matter          5
themed elements       7
species list          46   -> 8–53
Hebrew species        5    -> 54–58
English species       7    -> 59–65
Latin families        1    -> 66
Hebrew families       1    -> 67
Latin species         7    -> 68–74
whole names           1    -> 75
word elements         10   -> 76–85
notes                 2    -> 86–87
blank notes           2    -> 88–89
padding               2    -> 90–91
total                      -> 96 pages
```

The final sheet count must be a multiple of four. At 90 gsm the spine
formula is `(pages / 2) × 0.11 mm`; 96 pages give 5.28 mm.

## Cover

- Hebrew and Latin only; English appears only as bird names and element
  glosses, as in the book.
- Sand field, ochre accent, dark ink; no decorative stripes (they were mistaken
  for cutting marks and were removed).
- Author in Hebrew on the front. Back cover has Hebrew and Latin copy.
- The cover reads the interior page count and computes the spine; rebuild it
  after the interior is final.
- For a bindery that wants two cover files, `--split` writes
  `cover_front_print.pdf` and `cover_back_print.pdf`: 154 × 216 mm with 3 mm
  bleed, no spine band. The spread remains the primary cover file.

## Index system

Order after the species list:

| Index | Marker | Columns | Type | Status |
|---|---|---|---|---|
| Hebrew species | α | 3 | Hebrew names + refs | assembled 54–58 |
| English species | η | 2 | English names + refs | assembled 59–65 |
| Latin families | φ | 3 | Latin family + refs | assembled 66 |
| Hebrew families | μ | 3 | Hebrew family + refs | assembled 67 |
| Latin species | λ | 2 | Latin binomial + refs | assembled 68–74 |
| Whole names | σ | 1 | whole name + gloss + refs | assembled 75 |
| Word elements | ρ | 1 | element + page + Hebrew + group + refs | assembled 76–85 |

- Latin-script indexes (English, Latin family, Latin species, whole names,
  word elements) are laid out in reverse page order: the higher folio carries
  the earlier letter, so a physical left-to-right scan reads A–Z. The Hebrew
  indexes keep their right-to-left page order.
- μ is provisional (mnemonic: *mishpacha*). Easy to change.
- English is two columns because long names do not fit three: at 8.8 pt only
  65% fit, at 8.0 pt 80%; the longest English entry is about 54 mm against a
  37.3 mm three-column width.
- Latin species is also two columns: the longest binomial is about 56 mm at
  8.0 pt, and only 72% fit a 37.3 mm column. It is 7 pages (68–74).
- Latin and Hebrew family indexes are deliberately **separate**: a mixed
  Latin+Hebrew family row is data, not an index. Separate also makes three
  columns work; each family index is one page.
- Name indexes and the word-element index are pure: name + page reference
  only. The whole-name index is the one exception: it is a small glossary of
  non-decomposed names with a gloss and its source.
- References point to the first page of a family/species in the list
  (8–53).
- Letter headings repeat at the top of each column/page. The box shows the
  page's first and last letter.
- Word-element entries use the agreed format **glossary page first, then the
  list occurrence pages in parentheses**. The themed list of elements is
  content, separate from this index.
- The element index is one column and ten pages (76–85). The fixed row is
  Latin element (first letter aligned, leading hyphen hanging) · themed page ·
  Hebrew meaning · short group label · occurrence pages. Consecutive pages
  are compressed into ranges (`19–21`). Column titles run on every page:
  `מרכיב · עמוד · משמעות · קבוצה · עמודי רשימה`.
- The occurrence list is normally 7.8 pt; only the few longest lists shrink
  (to about 5.5–6.7 pt) so the fixed column is never broken and the element
  list never develops gaps.
- The old manual explanation was removed; the column titles do that work now.
- The themed data pages are titled `מרכיבי השמות לפי קבוצות` (not “מפתח”).
  Group headings are 15 pt bold — the same size as index letter headings —
  with a rule.
- Entries within each theme are sorted by Hebrew meaning and merged: one line
  carries every Latin form with that meaning, along with the English gloss and
  the Hebrew meaning once each. The forms share the line rather than repeating
  the meaning row by row.
- A long line of forms shrinks to stay on one line; English stays right-aligned
  in its column and the Hebrew meaning stays at the right edge. The longest
  nine-form group (bill) drops to about 5.6 pt; all other groups stay larger.
- This makes the themed section 7 pages (1–7).

## How to read this book

The key page (v) is organized under `סדר`, `סימונים`, `סימוני מינים` and
`מפתחות`. It carries the seven-index order, the data-versus-index distinction
and the grouped Latin forms. A short `רשימת חלופות` section after the species
markers explains that each line in the themed section gathers all the Latin
forms of one Hebrew meaning; the `סימונים` block explains the small
asterisk after a whole name. The Greek
letter in the margin is described as the index tag, with the page's first and
last letters below it. Each index row carries its mnemonic in parentheses —
אלפא, אתא, פי, מו, למבדא, סיגמא, רו — with the initial of the matching word bolded
(אלף־בית, אנגלית, family, משפחה, לטינית, שלם, רכיבים). The old taxonomic note was
condensed into the opening section; the Clements source remains on the
copyright page.

## Index markers

One box per index, not a wide range box:

- **19 mm tall × 4.2 mm wide**, outer fore-edge, 5 mm inside the trim: left
  on versos, right on rectos, so every tab is visible when riffling.
- One **20 mm slot** per index: α at the top, each following marker 20 mm
  lower. Seven indexes fit in 140 mm.
- Contents of the box: Greek letter at the top, a small gap, then the page's
  first and last letter in single letters (e.g. η / S / Z). If the page has one
  letter, it appears once.
- The box is fixed-size; do not add a next-letter line or subscript notation.
- These are printed margin markers, not cut thumb tabs; they identify the page
  when open or riffling, not a physical thumb index.
- The user decided not to add continuation/next-letter notation for now; if a
  letter split becomes a problem later, revisit.

## Typography and geometry

- Base text 10 pt; A5, 148 × 210 mm; text width 122 mm (13 mm side margins,
  14 mm top, 15 mm bottom).
- Latin: Noto Sans Mono (`BirdLatin`, `BirdLatinBold`).
- Hebrew: Droid Sans Hebrew (`BirdHebrew`, `BirdHebrewBold`); it has no ASCII
  punctuation, digits or Latin, so mixed text is drawn in font runs.
- Three-column index geometry: 5 mm gutters, 37.3 mm columns.
- Two-column index geometry: 6 mm gutter, 58 mm columns.
- Index type sizes: Hebrew species 8.8/7.8; English 8.0/7.2; Latin families
  8.2/7.4; Hebrew families 8.8/7.8. Letter headings 15 pt.
- K-only palette: K100 body, K75 secondary, K70 etymology, K60 labels, rules
  K35–K55. Cover stays RGB.

## Editing rules

- All printed prose is in `book/text.md`. The parser fails loudly on missing or
  duplicate keys.
- Hebrew values may contain ASCII punctuation, digits and Latin names; the
  renderer splits font runs automatically.
- Use the maqaf (`־`) and Hebrew geresh/gershayim (`׳` / `״`) inside Hebrew.
- A block line ending in `\` forces a hard line break.
- In a block, `כותרת: X` starts a section title and `- ` starts a bullet; the
  marker itself is not printed.
- `#` lines in `text.md` are notes, not printed.

## Hard-won lessons

- The old printed book tried to use a non-alphabetical list as an index; it did
  not work. Indexes must be alphabetical and pure. The themed element list is
  content and stays separate from the element index.
- A whole name that is exactly an element form (e.g. `alba`, `Anser`) is still
  a split and is set grey; exact matches were previously skipped and printed
  black. The source table now keeps only forms that occur in a name, and the
  build rejects unused forms; `Etymology.form_rows()` filters as a guard.
- Full-page-per-letter pagination is not acceptable: it wastes pages and
  creates many partial pages. Let large letters split; keep the marker simple.
- A combined Latin+Hebrew family row needed two columns because the row reached
  ~52 mm. Splitting the indexes let both use three columns.
- The user wants full absolute paths to proof PDFs, not relative paths.
- The full marker list and the mnemonic cue for each Greek letter are on the
  key page; keep this file's index table in step with it.

## Next work

1. Read the assembled interior and cover proofs end to end, checking the
   alternating edge tabs and the left-to-right Latin/English indexes.

## Lessons from the printed second edition

The printed second edition revealed the following on paper:

### Editorial

- Some tags are in the interior part of the book, making them useless.
  **Fixed:** the tab now follows the outer edge — left on versos, right on
  rectos.
- Latin (including English) indexes are right-to-left as the book is.
  This should be changed to left-to-right order. **Fixed:** Latin-script
  indexes are now assigned to pages in reverse order, so the higher folio
  carries the earlier letter and a physical left-to-right scan reads A–Z.
  This applies to the English species, Latin family, Latin species,
  whole-name and word-element indexes; the Hebrew indexes keep their
  right-to-left page order.

### Data

- `hispaniol` should be ספרד and not היספניול. **Fixed:** `hispaniol` is now
  `Spain` / `ספרד` in `data/in/etymology.md` (Jobling: *Hispaniolensis*
  Spanish, from L. *Hispania*, Spain).
- rubi- is classified as bramble פטל under מקום מחיה. Although one may be
  living in the bush itself — we should check what the meaning is.
  **Checked:** Jobling gives L. *rubus, rubi* bramble-bush, so the meaning is
  right and “Where it lives” remains the correct theme. The English gloss is
  now “bramble bush”.

These corrections are incorporated in the third edition.

## Don't

- Don't commit unless asked.
- Don't rebuild/print the cover while the page count is still moving.
- Don't mix index data into another index.
- Don't add explanatory subtitles to self-evident indexes.
