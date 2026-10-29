# Birds of Israel — working reference

Orientation notes for future sessions. Read this before changing the A5 book.

## Status

- The previous printed edition was 72 pages, perfect bound, A5 148 × 210 mm;
  five copies were printed.
- The current assembled interior is 96 pages: front matter, themed elements,
  species list, six indexes, two notes pages and five blanks. The cover has
  been rebuilt for the 5.28 mm spine.
- The interior is **K-only** (C=M=Y=0) and the logo is grayscale. The cover is
  full colour; colour inside was too expensive.
- The cover reads the interior's page count and derives the spine.

## Directory map

- `book/make_pocket.py` — the A5 interior builder.
- `book/make_cover.py` — the colour cover and spine.
- `book/text.md` — all printed prose; edit here, not in the builders.
- `book/book_text.py` — parser for `text.md` (`key: value`, `key: |`, `\` hard
  break).
- `book/mixed_text.py` — mixed Hebrew/Latin bidi and font-run rendering.
- `book/pocket_fonts.py` — font registration.
- `tools/etym.py` — etymology splits, glossary/index data and colours.
- `tools/make_book.py`, `tools/make_book_family.py` — shared Latin/Hebrew width
  and family layout helpers.
- `data/israel_birds_final.json` — species rows.
- `data/etymology.json` — element meanings, splits and themes.
- `data/israel_birds_merged.json` — source order used for the taxonomic list.
- `render.sh` — one command for interior + cover; `--one-file` for the copy
  shop sequence.
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

Build:

```sh
./render.sh                 # interior + cover
./render.sh --one-file      # cover front + interior + cover back
./render.sh --interior-only
./render.sh --cover-only
```

Preview the new indexes with their final folios (these do not touch the
assembled interior):

```sh
python3 book/make_pocket.py --preview-themes      # themed data, 1–7
python3 book/make_pocket.py --preview-themes-hebrew  # Hebrew-sorted output
python3 book/make_pocket.py --preview-key         # “How to read this book”
python3 book/make_pocket.py --preview-hebrew      # 3 columns, 54–58
python3 book/make_pocket.py --preview-hebrew --hebrew-columns 2
python3 book/make_pocket.py --preview-english     # 2 columns, 59–65
python3 book/make_pocket.py --preview-families    # Latin 66, Hebrew 67
python3 book/make_pocket.py --preview-latin-species  # 2 columns, 68–74
python3 book/make_pocket.py --preview-elements    # 1 column, 75–84
```

`pdfinfo`/`pdfunite` come from Poppler. `gs -sDEVICE=inkcov` is used to check
that interior pages stay K-only.

Outputs are in `out/book/`. Previews are proofs, not print files.

## Book structure (assembled)

- Front matter: five pages (title unnumbered; copyright ii, dedication iii,
  contents iv, key v).
- Themed word-element data: Arabic **1–7**, one column; this is content, not
  an index. Its title is `מרכיבי השמות לפי קבוצות`.
- Species list: Arabic **8–53**.
- Indexes: Arabic, in the order below.
- Notes: pages 85–86, then two blank note pages and printer padding to 96.
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
word elements         10   -> 75–84
notes                 2    -> 85–86
blank notes           2    -> 87–88
padding               3    -> 89–91
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

## Index system

Order after the species list:

| Index | Marker | Columns | Type | Status |
|---|---|---|---|---|
| Hebrew species | α | 3 | Hebrew names + refs | assembled 54–58 |
| English species | η | 2 | English names + refs | assembled 59–65 |
| Latin families | φ | 3 | Latin family + refs | assembled 66 |
| Hebrew families | μ | 3 | Hebrew family + refs | assembled 67 |
| Latin species | λ | 2 | Latin binomial + refs | assembled 68–74 |
| Word elements | ρ | 1 | element + page + Hebrew + group + refs | assembled 75–84 |

- μ is provisional (mnemonic: *mishpacha*). Easy to change.
- English is two columns because long names do not fit three: at 8.8 pt only
  65% fit, at 8.0 pt 80%; the longest English entry is about 54 mm against a
  37.3 mm three-column width.
- Latin species is also two columns: the longest binomial is about 56 mm at
  8.0 pt, and only 72% fit a 37.3 mm column. It is 7 pages (68–74).
- Latin and Hebrew family indexes are deliberately **separate**: a mixed
  Latin+Hebrew family row is data, not an index. Separate also makes three
  columns work; each family index is one page.
- Indexes are pure: name + page reference only. Do not add explanations or
  translations that belong to the data.
- References point to the first page of a family/species in the list
  (8–53).
- Letter headings repeat at the top of each column/page. The box shows the
  page's first and last letter.
- Word-element entries use the agreed format **glossary page first, then the
  list occurrence pages in parentheses**. The themed list of elements is
  content, separate from this index.
- The element index is one column and ten pages (75–84). The fixed row is
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
`מפתחות`. It carries the six-index order, the data-versus-index distinction
and the grouped Latin forms. A short `רשימת חלופות` section after the species
markers explains that each line in the themed section gathers all the Latin
forms of one Hebrew meaning. The Greek
letter in the margin is described as the index tag, with the page's first and
last letters below it. Each index row carries its mnemonic in parentheses —
אלפא, אתא, פי, מו, למבדא, רו — with the initial of the matching word bolded
(אלף־בית, אנגלית, family, משפחה, לטינית, רכיבים). The old taxonomic note was
condensed into the opening section; the Clements source remains on the
copyright page.

## Index markers

One box per index, not a wide range box:

- **19 mm tall × 4.2 mm wide**, left fore-edge, 5 mm inside the trim.
- One **20 mm slot** per index: α at the top, each following marker 20 mm
  lower. Six indexes fit in 120 mm.
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
- Full-page-per-letter pagination is not acceptable: it wastes pages and
  creates many partial pages. Let large letters split; keep the marker simple.
- A combined Latin+Hebrew family row needed two columns because the row reached
  ~52 mm. Splitting the indexes let both use three columns.
- The user wants full absolute paths to proof PDFs, not relative paths.
- The full marker list and the mnemonic cue for each Greek letter are on the
  key page; keep this file's index table in step with it.

## Next work

1. Read the assembled interior and cover proofs end to end.

## Don't

- Don't commit unless asked.
- Don't rebuild/print the cover while the page count is still moving.
- Don't mix index data into another index.
- Don't add explanatory subtitles to self-evident indexes.
