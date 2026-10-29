# Print brief — A5 pocket edition

## Files to send

1. **`out/book/israel_birds_pocket.pdf`** — interior.
   - 104 pages / 52 sheets.
   - A5, 148 × 210 mm.
   - **Black only** (K-only CMYK); print on a B/W device.
   - Single pages in reading order, no bleed.
   - Page 1 is the title page; the last five pages are intentionally blank
     (two note blanks and three printer blanks).

2. **`out/book/cover_spread.pdf`** — cover.
   - One page, 307.72 × 216 mm including 3 mm bleed.
   - Back + spine + front, outside only.
   - Spine 5.72 mm.
   - **Full colour.**

If the shop asks for a single file in reading order, run `./render.sh
--one-file`. It writes `out/book/israel_birds_one_file.pdf`: 106 A5 pages —
front cover, the 104-page interior, then the back cover. Its cover panels are
trimmed (no bleed); use `cover_spread.pdf` above for the actual cover printing.

A front panel alone (`cover_front_draft.pdf`) is a proof, produced only with
`python3 book/make_cover.py --front-only`; it is not part of the print set and
is not written by the normal build.

## Specification

- **Trim:** A5, 148 × 210 mm.
- **Extent:** 104 pages, including two blank note pages and three printer blanks
  at the end. Do not add or remove pages.
- **Binding:** perfect bound (paperback), softcover, spine 5.72 mm, no spine text.
- **Interior paper:** 90 gsm uncoated book paper. White gives the best contrast for the K-only text; cream/ivory is acceptable. Duplex. Grain parallel to the spine.
- **Cover paper:** 250 gsm white matte/silk card. 300 gsm is possible if the binder prefers it, but 250 gsm is easier to score at this spine. Print the outside only. Matte lamination outside recommended.
- **Colour:** interior **black only** — the PDF is K-only CMYK (C=M=Y=0), so print it on a B/W device; do not run it as colour. The cover is **full colour** and the PDF is RGB; convert it to CMYK with the profile for the chosen stock and provide a proof.
- **Cover press:** the cover sheet is 307.72 mm wide, so the press sheet must be
  at least 308 mm wide. SRA3 (320 × 450 mm) works; A3 (297 mm) and 12 × 18 in
  (304.8 mm) are too narrow. Print at 100%; do not scale or mirror.
- **Cover orientation:** back on the left, spine in the middle, front on the right, as supplied.
- **Fonts:** embedded; nothing to install.
- **Logo:** 869–1412 ppi, transparent background. The interior uses a grayscale copy; the cover logo is colour. If your RIP does not handle PDF transparency, ask for a flattened version.
- **Bleed/crop marks:** the cover has 3 mm bleed but no crop marks. Add crop marks if your workflow needs them. The interior has no bleed.

## Paper, spine and colour

The current spine is calculated for 90 gsm at 0.11 mm per sheet:

    52 sheets × 0.11 mm = 5.72 mm

If the shop uses a different stock, ask for its caliper and recalculate. Do not scale the cover to fit; regenerate it. Approximate uncoated values:

| Stock | Caliper (mm/sheet) | Spine at 104 pp |
|---|---:|---:|
| 80 gsm | 0.10 | 5.20 mm |
| 90 gsm | 0.11 | 5.72 mm (current) |
| 100 gsm | 0.12 | 6.24 mm |
| 120 gsm | 0.14 | 7.28 mm |

Actual caliper varies by paper. The bindery should confirm the final spine with the actual text block and cover stock. If they give a final spine, regenerate with:

```sh
python3 book/make_cover.py --pages 104 --spine 5.72
```

or, if working from caliper:

```sh
python3 book/make_cover.py --pages 104 --caliper 0.12
```

- **Interior colour:** print black only. White uncoated gives the best contrast for the K-only text; cream/ivory is acceptable. Avoid glossy interior stock.
- **Cover colour:** use white card, because the sand background is printed. Do not use cream cover board; it will tint the sand.
- **Cover finish:** matte lamination; gloss is not recommended for this palette.

## Print notes

- Keep the two blank note pages and the three printer blanks at the end. They
  are part of the 104-page count and the 5.72 mm spine.
- The interior side margins are 13 mm and the top margin 14 mm. Check the gutter in the proof. If the text feels tight at the binding edge, tell me before the full run; increasing the inner margin means repaginating.
- The cover is the outside only; the inside cover is unprinted. If your workflow needs a 4-page cover file (outside plus a blank inside), ask me.
- Print the cover spread as supplied; do not mirror it.
- The cover's example frames are 0.5 pt; the title rule is 1 pt. Check that they
  survive the proof.

## Proof checklist

- Spine width and wrap; the ochre spine band centred on the fold.
- Cover trim: the top edge is clean sand; both example frames and their text not clipped.
- Cover colour: sand `#EFDFC0`, ochre `#7A4E12`, frame fill `#FFF9EC`, frame border `#C9A96A`.
- Interior: no clipped text; Hebrew index columns; page numbers; K-only (no colour cast on the B/W proof); etymology `K70` clearly lighter than the `K100` text; rules `K35–K55` still visible.
- Binding: pages open cleanly and no text is lost in the gutter.

## Message you can send

Please quote and print this A5 perfect-bound paperback:

 - **Interior:** `israel_birds_pocket.pdf` — 104 pages, A5 148 × 210 mm, 90 gsm uncoated white (cream acceptable), duplex, **black only**.
 - **Cover:** `cover_spread.pdf` — 307.72 × 216 mm including 3 mm bleed, spine 5.72 mm, 250 gsm white matte/silk, matte lamination outside, **full colour**.
 - Perfect bound, no spine text. Grain parallel to the spine. Please provide a physical proof.
 - The cover needs SRA3 or larger (A3 is too narrow). Print at 100%; do not scale or mirror.
 - If you use a different paper, please tell me its caliper before printing; the spine must be recalculated, not scaled.
