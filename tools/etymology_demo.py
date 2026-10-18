#!/usr/bin/env python3
"""Layout specimen for etymological segmentation -- NOT part of the book yet.

Page 1  three ways of printing a split name, plus the split shown at the book's
        real half-column width so you can see it still fits.
Page 2  the fully self-contained variant, and what it costs.
Page 3  a mock-up of the glossary that would go at the end of the book.

Split notation used in the data below:

    "Phoenic|urus"     the | marks a morpheme boundary, printed as Phoenix·urus
    "rubec|~ula"       ~ marks a grammatical ending (can be tinted grey)
    "Erithacus"        no |: the name is not decomposable, printed whole

Run:
    python3 tools/etymology_demo.py --out out/etymology_layout_demo.pdf
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from make_book import (BLACK, FAINT, GREY, LIGHT_RULE, MID_RULE,
                       get_display, hebrew_text, register_fonts, wrap_words, w)

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

END_GREY = HexColor("#777777")
DOT_INK = HexColor("#4A4A4A")
BODY_INK = HexColor("#222222")
QUIET_INK = HexColor("#333333")

PAGE_W, PAGE_H = A4
# Exactly the book's page geometry, so the fit test on page 1 is the real one.
MARGIN_X, MARGIN_TOP, MARGIN_BOT = 11 * mm, 12 * mm, 12 * mm
BASE = 10.0                       # the book's species size
WIDTH = PAGE_W - 2 * MARGIN_X


# ---------------------------------------------------------------- specimens

ROWS = [
    dict(latin="Erithacus rubecula", hebrew="אדום-החזה",
         split="Erithacus rubec|~ula", gloss="ancient name · little red one"),
    dict(latin="Luscinia megarhynchos", hebrew="זמיר הירדן",
         split="Luscinia mega|rhynchos", gloss="nightingale · great bill"),
    dict(latin="Phoenicurus phoenicurus", hebrew="חכלילית עצים",
         split="Phoenic|urus phoenic|urus", gloss="crimson tail · crimson tail"),
    dict(latin="Monticola saxatilis", hebrew="צוקית חכלילית",
         split="Monti|cola sax|~atilis", gloss="mountain dweller · of rocks"),
    dict(latin="Saxicola rubicola", hebrew="דוחל שחור-גרון",
         split="Saxi|cola rubi|cola", gloss="rock dweller · bramble dweller"),
    dict(latin="Muscicapa striata", hebrew="חטפית אפורה",
         split="Musci|capa stri|~ata", gloss="fly catcher · striped"),
    dict(latin="Ficedula hypoleuca", hebrew="חטפית שחורת-עורף",
         split="Fic|edula hypo|leuca", gloss="fig eater · white beneath"),
    dict(latin="Oenanthe leucopyga", hebrew="סלעית שחורת-בטן",
         split="Oenanthe leuco|pyga", gloss="ancient plant name · white rump"),
]

# Two real genus blocks, drawn at the book's own column width.
IN_SITU = {
    "family": "Muscicapidae",
    "family_he": "חטפיתיים",
    "columns": [
        ("Ficedula", [
            ("Ficedula albicollis", "Fic|edula albi|collis", "חטפית לבנת-עורף"),
            ("Ficedula hypoleuca", "Fic|edula hypo|leuca", "חטפית שחורת-עורף"),
            ("Ficedula parva", "Fic|edula parva", "חטפית גמדית"),
            ("Ficedula semitorquata", "Fic|edula semi|torquata", "חטפית טורקית"),
        ]),
        ("Phoenicurus", [
            ("Phoenicurus erythronota", "Phoenic|urus erythro|nota", "חכלילית אדומת-גב"),
            ("Phoenicurus ochruros", "Phoenic|urus ochr|uros", "חכלילית סלעים"),
            ("Phoenicurus phoenicurus", "Phoenic|urus phoenic|urus", "חכלילית עצים"),
        ]),
    ],
}


# ---------------------------------------------------------------- splits

def parse_word(tok):
    """'rubec|~ula' -> [('rubec', 'root'), ('ula', 'end')]."""
    parts, buf, kind = [], "", "root"
    for ch in tok:
        if ch in "|~":
            if buf:
                parts.append((buf, kind))
                buf = ""
            if ch == "~":
                kind = "end"
        else:
            buf += ch
    if buf:
        parts.append((buf, kind))
    return parts


def parse_split(spec):
    return [parse_word(tok) for tok in spec.split()]


def char_w(size):
    return pdfmetrics.stringWidth("M", "BirdLatin", size)


def dot_adv(size):
    return char_w(size) * 0.72


def draw_dot(c, x, y, size):
    """A short raised dot. The font's U+00B7 sits on the baseline and reads as a
    full stop, which is exactly the wrong signal here."""
    c.setFillColor(DOT_INK)
    c.circle(x + dot_adv(size) / 2, y + size * 0.285, size * 0.052,
             stroke=0, fill=1)


def word_width(parts, size):
    total = sum(w(t, "BirdLatin", size) for t, _ in parts)
    return total + (len(parts) - 1) * dot_adv(size)


def split_width(words, size):
    gap = w(" ", "BirdLatin", size)
    return sum(word_width(parts, size) for parts in words) + gap * (len(words) - 1)


def draw_word(c, x, y, size, parts, tint):
    for i, (text, kind) in enumerate(parts):
        if i:
            draw_dot(c, x, y, size)
            x += dot_adv(size)
        c.setFillColor(END_GREY if (tint and kind == "end") else BLACK)
        c.setFont("BirdLatin", size)
        c.drawString(x, y, text)
        x += pdfmetrics.stringWidth(text, "BirdLatin", size)
    return x


def draw_split(c, x, y, size, words, tint):
    gap = w(" ", "BirdLatin", size)
    for j, parts in enumerate(words):
        draw_word(c, x, y, size, parts, tint)
        x += word_width(parts, size)
        if j < len(words) - 1:
            x += gap


# ---------------------------------------------------------------- furniture

def page_title(c, text, pno, total):
    top = PAGE_H - MARGIN_TOP
    c.setFillColor(BLACK)
    c.setFont("BirdLatin", BASE * 1.5)
    c.drawString(MARGIN_X, top - BASE * 1.5, text)
    c.setFillColor(GREY)
    c.setFont("BirdLatin", BASE * 0.82)
    c.drawRightString(PAGE_W - MARGIN_X, top - BASE * 1.5, f"{pno} / {total}")
    return top - BASE * 2.55


def body_text(c, x, y, text, width=WIDTH, size=None, colour=QUIET_INK, lead=1.05):
    size = size or BASE * 0.80
    c.setFillColor(colour)
    c.setFont("BirdLatin", size)
    for line in wrap_words(text, "BirdLatin", size, width):
        c.drawString(x, y, line)
        y -= size * lead
    return y


def section_title(c, x, y, letter, title, note, width=WIDTH):
    y -= BASE * 0.55
    c.setFillColor(BLACK)
    c.setFont("BirdLatin", BASE * 1.25)
    c.drawString(x, y, letter)
    c.setFont("BirdLatin", BASE * 1.05)
    c.drawString(x + 7 * mm, y, title)
    c.setFillColor(GREY)
    c.setFont("BirdLatin", BASE * 0.80)
    c.drawRightString(x + width, y, note)
    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.8)
    c.line(x, y - BASE * 0.55, x + width, y - BASE * 0.55)
    return y - BASE * 1.15


# ---------------------------------------------------------------- full-width rows

def draw_rows(c, x, y, rows, variant, width=WIDTH):
    """variant: 'dot' | 'tint' | 'gloss'."""
    tint = variant == "tint"
    for i, row in enumerate(rows):
        words = parse_split(row["split"])
        rh = BASE * (2.35 if variant == "gloss" else 1.62)
        baseline = (y - BASE * 1.02 if variant == "gloss"
                    else y - rh / 2 - BASE * 0.34)
        draw_split(c, x, baseline, BASE, words, tint)
        c.setFillColor(BLACK)
        c.setFont("BirdHebrew", BASE * 1.06)
        c.drawRightString(x + width, baseline,
                          get_display(hebrew_text(row["hebrew"])))
        if variant == "gloss":
            c.setFillColor(GREY)
            c.setFont("BirdLatin", BASE * 0.66)
            c.drawString(x, baseline - BASE * 1.02, row["gloss"])
        if i < len(rows) - 1:
            c.setStrokeColor(LIGHT_RULE)
            c.setLineWidth(0.4)
            c.line(x, y - rh, x + width, y - rh)
        y -= rh
    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.7)
    c.line(x, y, x + width, y)
    return y


# ---------------------------------------------------------------- in-situ panel

COL_W = (WIDTH - 7 * mm) / 2


def draw_in_situ(c, y):
    fam_size = BASE * 1.46
    genus_size = BASE * 1.24
    row_h = BASE * 1.62
    rule_gap = 1.1 * mm
    head_h = fam_size * 1.4 + 2.4 * mm

    bottom = y
    widest = 0.0
    for ci, (genus, species) in enumerate(IN_SITU["columns"]):
        x = MARGIN_X + ci * (COL_W + 7 * mm)

        c.setFillColor(BLACK)
        c.setFont("BirdLatin", fam_size)
        c.drawString(x, y - fam_size * 0.92, IN_SITU["family"])
        c.setFillColor(GREY)
        c.setFont("BirdHebrew", fam_size * 0.95)
        c.drawRightString(x + COL_W, y - fam_size * 0.92,
                          get_display(hebrew_text(IN_SITU["family_he"])))
        c.setStrokeColor(HexColor("#3A3A3A"))
        c.setLineWidth(1.1)
        c.line(x, y - fam_size * 1.4, x + COL_W, y - fam_size * 1.4)

        gy = y - head_h
        c.setFillColor(BLACK)
        c.setFont("BirdLatin", genus_size)
        c.drawString(x, gy - genus_size * 0.88, genus)
        rule_y = gy - genus_size * 1.05 - rule_gap * 0.5
        c.setStrokeColor(MID_RULE)
        c.setLineWidth(0.7)
        c.line(x, rule_y, x + COL_W, rule_y)

        avail = COL_W - 5 * mm          # what the book lets a row use
        for i, (latin, split, hebrew) in enumerate(species):
            slot_top = rule_y - i * row_h
            baseline = slot_top - row_h / 2 - BASE * 0.34
            words = parse_split(split)
            draw_split(c, x, baseline, BASE, words, False)
            heb_w = w(hebrew, "BirdHebrew", BASE * 1.06, rtl=True)
            c.setFillColor(BLACK)
            c.setFont("BirdHebrew", BASE * 1.06)
            c.drawRightString(x + COL_W, baseline,
                              get_display(hebrew_text(hebrew)))
            widest = max(widest, (split_width(words, BASE) + heb_w) / avail)
            if split_width(words, BASE) + heb_w > avail:
                raise SystemExit(f"row would be shrunk in the book: {latin}")
            if i < len(species) - 1:
                c.setStrokeColor(LIGHT_RULE)
                c.setLineWidth(0.4)
                c.line(x, slot_top - row_h, x + COL_W, slot_top - row_h)

        c.setStrokeColor(MID_RULE)
        c.setLineWidth(0.7)
        c.line(x, rule_y - len(species) * row_h,
               x + COL_W, rule_y - len(species) * row_h)
        bottom = min(bottom, rule_y - len(species) * row_h)

    return bottom - BASE * 1.25, widest


# ---------------------------------------------------------------- page 1

def page_one(c, total):
    y = page_title(c, "Splitting the names", 1, total)
    y = body_text(c, MARGIN_X, y,
                  "Everything else on the row stays as it is: one line per species, Latin "
                  "left, Hebrew right, same type size. Only the Latin name gains a mark. "
                  "The meaning of the parts lives in the glossary at the end.") - BASE * 0.9

    # A and B on the same eight rows, side by side at the book's own column width
    bottoms = []
    for ci, (letter, title, variant) in enumerate((
            ("A", "Raised dot only", "dot"),
            ("B", "Dot + grey endings", "tint"))):
        x = MARGIN_X + ci * (COL_W + 7 * mm)
        c.setFillColor(BLACK)
        c.setFont("BirdLatin", BASE * 1.15)
        c.drawString(x, y, letter)
        c.setFont("BirdLatin", BASE * 0.96)
        c.drawString(x + 7 * mm, y, title)
        c.setStrokeColor(MID_RULE)
        c.setLineWidth(0.8)
        c.line(x, y - BASE * 0.55, x + COL_W, y - BASE * 0.55)
        bottoms.append(draw_rows(c, x, y - BASE * 1.25, ROWS, variant, width=COL_W))
    y = min(bottoms) - BASE * 1.35

    y, widest = draw_in_situ(
        c, section_title(c, MARGIN_X, y, "C", "In place, at the book's column width",
                         "family, genus and species, exactly as they will print") - BASE * 0.45)

    y = section_title(c, MARGIN_X, y, "D", "Dot plus a plain-English gloss",
                      "self-contained, but the row is ~45% taller") - BASE * 0.45
    y = draw_rows(c, MARGIN_X, y, ROWS, "gloss") - BASE * 1.5

    y = body_text(c, MARGIN_X, y,
                  f"The widest row in this sample uses {widest:.0%} of the width a row is "
                  "allowed, Hebrew included. Variants A and B cost no pages: the fitting loop "
                  "only shrinks a genus where it was already at the limit. The gloss variant "
                  "would take the 17-page book to roughly 24.") - BASE * 0.7
    body_text(c, MARGIN_X, y,
              "Not every name decomposes. Upupa epops is echoic — the bird says its own name. "
              "Oenanthe is an ancient plant name reused for the wheatears. Turdus and Merula "
              "are simply what the Romans called those birds. These print whole, with no dot, "
              "and are glossed in a 'names, not words' section rather than given an invented "
              "meaning.", colour=GREY, size=BASE * 0.78)
    c.showPage()


# ---------------------------------------------------------------- page 2

GLOSSARY = [
    ("Colour", [
        ("phoenic-", "crimson, purple-red", "ארגמן", "Phoenicurus, Phoenicopterus"),
        ("rub-", "red", "אדום", "Erithacus rubecula"),
        ("melan-", "black", "שחור", "Oenanthe melanura"),
        ("atr-", "dull black", "שחור", "Turdus atrogularis"),
        ("leuc-", "white", "לבן", "Oenanthe leucopyga"),
        ("alb-", "white", "לבן", "Motacilla alba"),
        ("cyan-", "blue", "כחול", "Tarsiger cyanurus"),
        ("xanth-", "yellow", "צהוב", "Oenanthe xanthoprymna"),
        ("chrys-", "golden", "זהוב", "Oenanthe chrysopygia"),
    ]),
    ("Body", [
        ("-rhynchos", "bill", "מקור", "Luscinia megarhynchos"),
        ("-ura", "tail", "זנב", "Phoenicurus"),
        ("-pyga", "rump", "שת", "Oenanthe leucopyga"),
        ("-collis", "neck", "צוואר", "Ficedula albicollis"),
        ("guttur-", "throat", "גרון", "Irania gutturalis"),
    ]),
    ("Size and shape", [
        ("mega-", "great, large", "גדול", "Luscinia megarhynchos"),
        ("micro-", "small", "קטן", "Microcarbo"),
        ("brachy-", "short", "קצר", "Certhia brachydactyla"),
        ("platy-", "broad, flat", "רחב", "Anas platyrhynchos"),
    ]),
    ("Place and habit", [
        ("-cola", "dweller", "שוכן", "Saxicola, Monticola"),
        ("sax-", "rock", "סלע", "Monticola saxatilis"),
        ("mont-", "mountain", "הר", "Monticola"),
        ("-ensis", "of a place", "של מקום", "Halcyon smyrnensis"),
    ]),
    ("Grammar", [
        ("-ula", "little (diminutive)", "הקטנה", "Erithacus rubecula"),
        ("-ata", "provided with", "בעל", "Muscicapa striata"),
        ("-arius", "belonging to", "של", "Monticola solitarius"),
    ]),
    ("Names, not words", [
        ("Upupa", "imitates the call", "חיקוי הקריאה", "Upupa epops"),
        ("-ii", "named after a person", "על שם אדם", "Oenanthe finschii"),
    ]),
]


def page_two(c, total):
    y = page_title(c, "Word elements", 2, total)
    y = body_text(c, MARGIN_X, y,
                  "Read a hyphen as an anchor, not punctuation: phoenic- begins a compound, "
                  "-ura ends one, -cola means the word is the second half. The dot in the book "
                  "marks exactly those joints.") - BASE * 0.55

    x_elem = MARGIN_X
    w_elem = 34 * mm
    x_en = x_elem + w_elem
    w_en = 54 * mm
    x_he_right = x_en + w_en + 30 * mm
    x_ex = x_he_right + 6 * mm
    row_h = BASE * 1.32

    for theme, entries in GLOSSARY:
        y -= BASE * 1.9
        c.setFillColor(BLACK)
        c.setFont("BirdLatin", BASE * 0.80)
        c.drawString(x_elem, y, theme.upper())
        c.setStrokeColor(MID_RULE)
        c.setLineWidth(0.7)
        c.line(x_elem, y - BASE * 0.42, MARGIN_X + WIDTH, y - BASE * 0.42)
        y -= BASE * 1.05

        for idx, (elem, en, he, ex) in enumerate(entries):
            c.setFillColor(BLACK)
            c.setFont("BirdLatin", BASE * 0.92)
            c.drawString(x_elem, y - BASE * 0.72, elem)

            c.setFillColor(BODY_INK)
            c.setFont("BirdLatin", BASE * 0.84)
            c.drawString(x_en, y - BASE * 0.72, en)

            c.setFillColor(BODY_INK)
            c.setFont("BirdHebrew", BASE * 0.90)
            c.drawRightString(x_he_right, y - BASE * 0.72,
                              get_display(hebrew_text(he)))

            c.setFillColor(FAINT)
            c.setFont("BirdLatin", BASE * 0.74)
            c.drawString(x_ex, y - BASE * 0.72, ex)

            if idx < len(entries) - 1:
                c.setStrokeColor(LIGHT_RULE)
                c.setLineWidth(0.35)
                c.line(x_elem, y - row_h, MARGIN_X + WIDTH, y - row_h)
            y -= row_h
    c.showPage()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/etymology_layout_demo.pdf")
    args = ap.parse_args()

    register_fonts()
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    c = canvas.Canvas(args.out, pagesize=A4)
    c.setTitle("Birds of Israel — etymology layout specimen")
    page_one(c, 2)
    page_two(c, 2)
    c.save()
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
