#!/usr/bin/env python3
"""Cover for the A5 pocket edition.

All printed prose lives in ``book/text.md``; this file places it.  Design: a
13-band chromatic strip (one band per etymology theme) across the head, the
Closing in on Birds mark, a Hebrew-led title, and the examples set in light
cream frames on both panels.  The front frame holds the European robin; the
back frame holds the Namaqua dove and Eurasian nightjar, with the word elements
of both.  The bird blocks use Latin / English / Hebrew in the book's order; the
word elements sit in a separate left-aligned list inside the same frame, so
they do not read as extra columns of the bird row.  There are no invented
equals signs.

Outputs (all with 3 mm bleed):
  out/book/cover_front_draft.pdf
  out/book/cover_spread.pdf      (back + spine + front)

The trim size is 148 x 210 mm.  Run after make_pocket.py so the page count is
known for the spine; the count is read from the built interior, or pass
--pages explicitly.
"""

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from bidi.algorithm import get_display
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

import book_text
import make_book as mb
import pocket_fonts
from make_book import hebrew_text, w
from etym import PART_GREY, Etymology

TRIM_W, TRIM_H = 148 * mm, 210 * mm
BLEED = 3 * mm

SAND = HexColor("#EFDFC0")
ACCENT = HexColor("#7A4E12")
INK = HexColor("#2F2714")
QUIET = HexColor("#4A4034")
FAINT = HexColor("#8A7A5E")

BANDS = [
    "#7A4E12", "#A65E22", "#C97B2E", "#ECB652", "#D8C08A",
    "#9A9A5B", "#5F7F55", "#2F5D62", "#3E6B89", "#6B5B95",
    "#9B4F4F", "#C97B63", "#5A4A42",
]

LOGO = os.path.join(ROOT, "book", "assets", "logo_circle.png")

SPECIES_PATH = os.path.join(ROOT, "data", "israel_birds_final.json")
with open(SPECIES_PATH, encoding="utf-8") as _f:
    SPECIES = {sp["latin"]: sp for sp in json.load(_f)}

FRONT_SPECIES = "Erithacus rubecula"
BACK_SPECIES = ("Oena capensis", "Caprimulgus europaeus")

TEXT_PATH = os.path.join(ROOT, "book", "text.md")
T = book_text.Text(TEXT_PATH)

TITLE_HE = T["book.title_he"]
SUBTITLE_HE = T["book.subtitle_he"]
TITLE_EN = T["book.title_en"]
SUBTITLE_EN = T["book.subtitle_en"]
EDITION = T["book.edition"]
AUTHOR = T["book.author"]


def he(s):
    return get_display(hebrew_text(s))


def register():
    return pocket_fonts.register()


def centred_chars(c, x, y, text, font, size, tracking=0.0):
    """Draw centred text with extra tracking (for the English title)."""
    if not tracking:
        c.setFont(font, size)
        c.drawCentredString(x, y, text)
        return
    total = sum(w(ch, font, size) for ch in text) + tracking * (len(text) - 1)
    cx = x - total / 2
    c.setFont(font, size)
    for ch in text:
        c.drawString(cx, y, ch)
        cx += w(ch, font, size) + tracking


def example_elements(etym, sp):
    """The split parts of the epithet, as the element index would show them."""
    parts = etym.splits.get(sp["epithet"]) or etym.splits.get(sp["genus"]) or []
    rows = []
    for i, (surface, eid) in enumerate(parts):
        el = etym.elements[eid]
        shown = surface.lower()
        if i == len(parts) - 1 and len(parts) > 1:
            shown = "-" + shown
        rows.append((shown, el["en"], el["he"]))
    return rows


def draw_cover_latin(c, x, y, sp, etym, size):
    """Draw the binomial in the book's etymology colours, with raised dots."""
    gap = w(" ", "BirdLatin", size)
    for i, word in enumerate((sp["genus"], sp["epithet"])):
        if i:
            x += gap
        parts = etym.splits.get(word)
        if not parts:
            c.setFillColor(INK)
            c.setFont("BirdLatin", size)
            c.drawString(x, y, word)
            x += w(word, "BirdLatin", size)
            continue
        c.setFont("BirdLatin", size)
        for j, (surface, _) in enumerate(parts):
            if j:
                etym._dot(c, x, y, size)
                x += etym._dot_adv(size, "BirdLatin")
            c.setFillColor(PART_GREY)
            c.drawString(x, y, surface)
            x += w(surface, "BirdLatin", size)
    return x


def draw_bird(c, left, right, family_y, sp, etym, line=8 * mm,
              en_gap=40 * mm):
    """Family, then the species row (Latin, English, Hebrew).

    The word elements are deliberately not drawn here: they go in a separate
    left-aligned list so they do not read as extra columns of the bird row.
    """
    x_en = left + en_gap

    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 6.8)
    c.drawString(left, family_y, sp["family"])
    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 7.0)
    c.drawRightString(right, family_y, he(sp["family_he"]))

    y = family_y - line
    draw_cover_latin(c, left, y, sp, etym, 7.8)
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 6.2)
    c.drawString(x_en, y, sp["english"])
    c.setFillColor(INK)
    c.setFont("BirdHebrew", 7.6)
    c.drawRightString(right, y, he(sp["hebrew"]))


def draw_elements(c, x, y, rows, line=6 * mm, size=7.0):
    """A left-aligned list inside the example frame: element, English, Hebrew.

    Each line flows from the left with fixed gaps.  The meanings do not line up
    with the bird row above, because they are a separate list, not a column of
    the species entry.
    """
    for shown, en, heb in rows:
        c.setFillColor(INK)
        c.setFont("BirdLatin", size)
        c.drawString(x, y, shown)

        ex = x + w(shown, "BirdLatin", size) + 3 * mm
        c.setFillColor(QUIET)
        c.setFont("BirdLatin", size * 0.88)
        c.drawString(ex, y, en)

        hx = ex + w(en, "BirdLatin", size * 0.88) + 3 * mm
        c.setFillColor(INK)
        c.setFont("BirdHebrew", size * 1.03)
        c.drawString(hx, y, he(heb))

        y -= line


def draw_front(c, x0, y0, etym):
    """Draw the front cover in trim coordinates, offset by (x0, y0)."""
    W, H = TRIM_W, TRIM_H

    # ---- sand field, edge to edge (bleed comes from the page size)
    c.setFillColor(SAND)
    c.rect(x0 - BLEED, y0 - BLEED, W + 2 * BLEED, H + 2 * BLEED,
           stroke=0, fill=1)

    # ---- 13-band strip, bled to the top and sides
    band_w = (W + 2 * BLEED) / 13.0
    top = y0 + H
    for i, col in enumerate(BANDS):
        c.setFillColor(HexColor(col))
        c.rect(x0 - BLEED + i * band_w, top - 14 * mm,
               band_w + 0.15, 14 * mm + BLEED, stroke=0, fill=1)

    # ---- mark
    lw = 52 * mm
    lh = lw * 1705 / 1779
    c.drawImage(LOGO, x0 + (W - lw) / 2, y0 + H - 26 * mm - lh,
                lw, lh, mask="auto")

    # ---- title, Hebrew first
    cx = x0 + W / 2
    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 26)
    c.drawCentredString(cx, y0 + 116 * mm, he(TITLE_HE))
    c.setFont("BirdHebrew", 11.5)
    c.drawCentredString(cx, y0 + 103 * mm, he(SUBTITLE_HE))

    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.0)
    c.line(x0 + 52 * mm, y0 + 95 * mm, x0 + 96 * mm, y0 + 95 * mm)

    c.setFillColor(ACCENT)
    centred_chars(c, cx, y0 + 82 * mm, TITLE_EN, "BirdLatinBold", 15.0, 1.4)
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 8.6)
    c.drawCentredString(cx, y0 + 72 * mm, SUBTITLE_EN)

    # ---- author, before the example
    c.setFillColor(INK)
    c.setFont("BirdLatin", 9.5)
    c.drawCentredString(cx, y0 + 58.5 * mm, AUTHOR)

    # ---- example card: family, species row and word elements in one frame
    left, right = x0 + 24 * mm, x0 + 124 * mm
    c.setFillColor(HexColor("#FFF9EC"))
    c.setStrokeColor(HexColor("#C9A96A"))
    c.setLineWidth(0.5)
    c.rect(left, y0 + 17 * mm, right - left, 33 * mm, stroke=1, fill=1)

    content_left = left + 5 * mm
    content_right = right - 5 * mm
    draw_bird(c, content_left, content_right, y0 + 45 * mm,
              SPECIES[FRONT_SPECIES], etym, line=8 * mm, en_gap=40 * mm)
    draw_elements(c, content_left, y0 + 29 * mm,
                  example_elements(etym, SPECIES[FRONT_SPECIES]),
                  line=7 * mm)

    # ---- foot
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 6.8)
    c.drawCentredString(cx, y0 + 11 * mm, T["cover.front_footer"])


def draw_back(c, x0, y0, etym):
    W, H = TRIM_W, TRIM_H
    c.setFillColor(SAND)
    c.rect(x0 - BLEED, y0 - BLEED, W + 2 * BLEED, H + 2 * BLEED,
           stroke=0, fill=1)

    lw = 32 * mm
    lh = lw * 1705 / 1779
    c.drawImage(LOGO, x0 + (W - lw) / 2, y0 + H - 26 * mm - lh,
                lw, lh, mask="auto")

    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 15)
    c.drawCentredString(x0 + W / 2, y0 + 138 * mm, he(TITLE_HE))
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 9.5)
    c.drawCentredString(x0 + W / 2, y0 + 128 * mm, TITLE_EN)
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 8)
    c.drawCentredString(x0 + W / 2, y0 + 119 * mm,
                        T["cover.back_subtitle"])

    # Everything below the subtitle is left-aligned on one edge.
    x_text = x0 + 20 * mm
    text_w = 108 * mm
    y = y0 + 108 * mm
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 8.6)
    for para in (T["cover.back_para_1"], T["cover.back_para_2"]):
        for line in mb.wrap_words(para, "BirdLatin", 8.6, text_w):
            c.drawString(x_text, y, line)
            y -= 12.5
        y -= 8

    # ---- example frame: both birds and their word elements together
    fx, fy = x0 + 16 * mm, y0 + 14 * mm
    fw, fh = 116 * mm, 66 * mm
    c.setFillColor(HexColor("#FFF9EC"))
    c.setStrokeColor(HexColor("#C9A96A"))
    c.setLineWidth(0.5)
    c.rect(fx, fy, fw, fh, stroke=1, fill=1)

    bird1_y = y0 + 74 * mm
    draw_bird(c, x_text, x_text + text_w, bird1_y,
              SPECIES[BACK_SPECIES[0]], etym, line=8 * mm, en_gap=46 * mm)

    bird2_y = y0 + 56 * mm
    draw_bird(c, x_text, x_text + text_w, bird2_y,
              SPECIES[BACK_SPECIES[1]], etym, line=8 * mm, en_gap=46 * mm)

    rows = (example_elements(etym, SPECIES[BACK_SPECIES[0]])
            + example_elements(etym, SPECIES[BACK_SPECIES[1]]))
    draw_elements(c, x_text, y0 + 38 * mm, rows, line=6 * mm)

    c.setFillColor(FAINT)
    c.setFont("BirdLatin", 7.0)
    c.drawString(x_text, y0 + 8 * mm, EDITION)


def spine_width(pages, caliper=0.11):
    """Spine = sheets x paper caliper.  0.11 mm/sheet is 90 gsm uncoated."""
    return max(2.0, (pages / 2.0) * caliper) * mm


def count_pages(path):
    """Page count from the built interior, so the spine cannot drift."""
    try:
        out = subprocess.run(["pdfinfo", path], capture_output=True,
                             text=True, check=True).stdout
        return int(re.search(r"^Pages:\s+(\d+)", out, re.M).group(1))
    except Exception:
        return 72


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=0,
                    help="interior page count; 0 = read it from the built PDF")
    ap.add_argument("--caliper", type=float, default=0.11,
                    help="paper caliper in mm per sheet (default 0.11 for "
                         "90 gsm uncoated)")
    ap.add_argument("--spine", type=float, default=0,
                    help="final spine width in mm; overrides --caliper")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "book"))
    ap.add_argument("--front-only", action="store_true")
    args = ap.parse_args()

    register()
    etym = Etymology(os.path.join(ROOT, "data", "etymology.json"))
    os.makedirs(args.out, exist_ok=True)
    if not args.pages:
        args.pages = count_pages(os.path.join(args.out, "israel_birds_pocket.pdf"))

    # Front cover, trim + bleed.
    pw, ph = TRIM_W + 2 * BLEED, TRIM_H + 2 * BLEED
    front = os.path.join(args.out, "cover_front_draft.pdf")
    c = canvas.Canvas(front, pagesize=(pw, ph),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle("Birds of Israel — cover")
    c.setAuthor(AUTHOR)
    draw_front(c, BLEED, BLEED, etym)
    c.showPage()
    c.save()
    print(f"Wrote {front}  ({pw / mm:.0f} x {ph / mm:.0f} mm, 3 mm bleed)")

    if args.front_only:
        return

    # Full spread: back + spine + front.
    sp = (args.spine * mm) if args.spine else spine_width(args.pages,
                                                          args.caliper)
    sw = 2 * TRIM_W + sp + 2 * BLEED
    sh = TRIM_H + 2 * BLEED
    spread = os.path.join(args.out, "cover_spread.pdf")
    c = canvas.Canvas(spread, pagesize=(sw, sh),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle("Birds of Israel — cover spread")
    c.setAuthor(AUTHOR)

    # Sand across the whole spread first, so the spine has no seams.
    c.setFillColor(SAND)
    c.rect(0, 0, sw, sh, stroke=0, fill=1)

    draw_back(c, BLEED, BLEED, etym)
    front_x = BLEED + TRIM_W + sp
    draw_front(c, front_x, BLEED, etym)

    # Spine: a single ochre band with the title running up it if it is wide
    # enough to set type; at ~4 mm it is left as colour.
    c.setFillColor(HexColor(BANDS[0]))
    c.rect(BLEED + TRIM_W, 0, sp, sh, stroke=0, fill=1)

    c.showPage()
    c.save()
    print(f"Wrote {spread}  (spine {sp / mm:.2f} mm for {args.pages} pages)")


if __name__ == "__main__":
    main()
