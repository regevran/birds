# Print brief — A5 pocket edition

## Files to send

1. **`out/book/israel_birds_pocket.pdf`** — interior.
   - 72 pages / 36 sheets.
   - A5, 148 × 210 mm.
   - Single pages in reading order, no bleed.
   - Page 1 is the title page; the last page is intentionally blank.

2. **`out/book/cover_spread.pdf`** — cover.
   - One page, 305.96 × 216 mm including 3 mm bleed.
   - Back + spine + front, outside only.
   - Spine 3.96 mm.

A front panel alone (`cover_front_draft.pdf`) is a proof, produced only with
`python3 book/make_cover.py --front-only`; it is not part of the print set and
is not written by the normal build.

## Specification

- **Trim:** A5, 148 × 210 mm.
- **Extent:** 72 pages, including the blank last page. Do not add or remove pages.
- **Binding:** perfect bound (paperback), softcover, spine 3.96 mm, no spine text.
- **Interior paper:** 90 gsm uncoated book paper. Cream/ivory is the natural match for the warm palette; white is also fine. Duplex. Grain parallel to the spine.
- **Cover paper:** 250 gsm white matte/silk card. 300 gsm is possible if the binder prefers it, but 250 gsm is easier to score at this spine. Print the outside only. Matte lamination outside recommended.
- **Colour:** full colour. The interior has an ochre accent; do not print it grayscale. The PDFs are RGB; convert to CMYK if your workflow needs it, and please provide a proof.
- **Cover press:** the cover sheet is 305.96 mm wide, so the press sheet must be
  at least 306 mm wide. SRA3 (320 × 450 mm) works; A3 (297 mm) and 12 × 18 in
  (304.8 mm) are too narrow. Print at 100%; do not scale or mirror.
- **Cover orientation:** back on the left, spine in the middle, front on the right, as supplied.
- **Fonts:** embedded; nothing to install.
- **Logo:** 869–1412 ppi, transparent background. If your RIP does not handle PDF transparency, ask for a flattened version.
- **Bleed/crop marks:** the cover has 3 mm bleed but no crop marks. Add crop marks if your workflow needs them. The interior has no bleed.

## Paper, spine and colour

The current spine is calculated for 90 gsm at 0.11 mm per sheet:

    36 sheets × 0.11 mm = 3.96 mm

If the shop uses a different stock, ask for its caliper and recalculate. Do not scale the cover to fit; regenerate it. Approximate uncoated values:

| Stock | Caliper (mm/sheet) | Spine at 72 pp |
|---|---:|---:|
| 80 gsm | 0.10 | 3.60 mm |
| 90 gsm | 0.11 | 3.96 mm (current) |
| 100 gsm | 0.12 | 4.32 mm |
| 120 gsm | 0.14 | 5.04 mm |

Actual caliper varies by paper. The bindery should confirm the final spine with the actual text block and cover stock. If they give a final spine, regenerate with:

```sh
python3 book/make_cover.py --pages 72 --spine 4.2
```

or, if working from caliper:

```sh
python3 book/make_cover.py --pages 72 --caliper 0.12
```

- **Interior colour:** cream/ivory uncoated is warm and suits the sand/ochre palette; white is crisper. Avoid glossy interior stock.
- **Cover colour:** use white card, because the sand background is printed. Do not use cream cover board; it will tint the sand.
- **Cover finish:** matte lamination; gloss is not recommended for this palette.

## Print notes

- Keep the last blank page. It is part of the 72-page count and the 3.96 mm spine.
- The interior side margins are 13 mm and the top margin 14 mm. Check the gutter in the proof. If the text feels tight at the binding edge, tell me before the full run; increasing the inner margin means repaginating.
- The cover is the outside only; the inside cover is unprinted. If your workflow needs a 4-page cover file (outside plus a blank inside), ask me.
- Print the cover spread as supplied; do not mirror it.
- The cover's example frames are 0.5 pt; the title rule is 1 pt. Check that they
  survive the proof.

## Proof checklist

- Spine width and wrap; the ochre spine band centred on the fold.
- Cover trim: the 13-band strip at the head; both example frames and their text not clipped.
- Cover colour: sand `#EFDFC0`, ochre `#7A4E12`, frame fill `#FFF9EC`, frame border `#C9A96A`.
- Interior: no clipped text; Hebrew index columns; page numbers; grey etymology `#5A5A5A`; ochre accent `#7A4E12`.
- Binding: pages open cleanly and no text is lost in the gutter.

## Message you can send

Please quote and print this A5 perfect-bound paperback:

 - **Interior:** `israel_birds_pocket.pdf` — 72 pages, A5 148 × 210 mm, 90 gsm uncoated cream/ivory (white acceptable), duplex.
 - **Cover:** `cover_spread.pdf` — 305.96 × 216 mm including 3 mm bleed, spine 3.96 mm, 250 gsm white matte/silk, matte lamination outside.
 - Perfect bound, no spine text. Grain parallel to the spine. Full colour. Please provide a physical proof.
 - The cover needs SRA3 or larger (A3 is too narrow). Print at 100%; do not scale or mirror.
 - If you use a different paper, please tell me its caliper before printing; the spine must be recalculated, not scaled.
