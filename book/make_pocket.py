#!/usr/bin/env python3
"""Birds of Israel — A5 pocket edition (perfect-bound softcover).

A separate work from the A4 learning sheets.  All printed prose lives in
``book/text.md``; this file places it.  It reads the same source data
(``data/israel_birds_final.json`` and ``data/etymology.json``) but has its own
layout, front matter, colour and indexes:

  * A5 (148 x 210 mm), one text column, 10 pt species type;
  * front matter: title, copyright, contents, key (unnumbered);
  * body: families alphabetical, genus blocks, Latin · English · Hebrew;
  * Hebrew name index, alphabetised in Hebrew, with page references;
  * index of word elements (etymology), one column at A5;
  * ruled notes page and padding to a multiple of four pages.

Output: out/book/israel_birds_pocket.pdf

Run:
    python3 book/make_pocket.py
"""

import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from bidi.algorithm import get_display
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

import book_text
import make_book as mb
import make_book_family as mf
import pocket_fonts
from make_book import (FAINT, GREY, LIGHT_RULE, MID_RULE,
                       hebrew_text, w, wrap_words)
from etym import Etymology

# ---------------------------------------------------------------- identity

TEXT_PATH = os.path.join(ROOT, "book", "text.md")
T = book_text.Text(TEXT_PATH)

TITLE_HE = T["book.title_he"]
SUBTITLE_HE = T["book.subtitle_he"]
TITLE_EN = T["book.title_en"]
SUBTITLE_EN = T["book.subtitle_en"]
EDITION = T["book.edition"]
AUTHOR = T["book.author"]

LEGEND_TEXT = [
    ("A", T["key.legend_a"]),
    ("I", T["key.legend_i"]),
    ("Ex", T["key.legend_ex"]),
    ("X", T["key.legend_x"]),
    ("—", T["key.legend_none"]),
]

LOGO = os.path.join(ROOT, "book", "assets", "logo_circle.png")

# Warm palette taken from the cover logo (ochre #ECB652 on dark ink).
ACCENT = HexColor("#7A4E12")
ACCENT_RULE = HexColor("#B99A62")
INK = HexColor("#2F2714")
QUIET = HexColor("#4A4034")
SAND = HexColor("#F3E7CD")
PAPER = HexColor("#FFFDF7")

# Index metrics (points).
ETYM_ROW, ETYM_THEME = 10.8, 19.0
HEB_ROW, HEB_LETTER = 10.8, 20.0

# Three-field species row.  English has a fixed column; Latin shrinks only if
# a name would cross into it.
EN_COL = 52 * mm          # English column, measured from the text edge
EN_RATIO = 0.70           # 7.0 pt at the 10 pt base
HE_RATIO = 0.98           # 9.8 pt; keeps the Hebrew optically level with Latin
MARK_RATIO = 0.64         # marker type, incl. parentheses
FIELD_GAP = 3 * mm
MARK_GAP = 1.5 * mm

# Taxonomic order heading (orders above families in the list).
ORDER_H = 7 * mm

# Contents and notes.
NOTES_ROWS = 24


def register_fonts():
    return pocket_fonts.register()


def heb(s):
    return get_display(hebrew_text(s))


_PUNCT_METRICS = None


def punct_rsb(ch, size):
    """Right side bearing of a Latin punctuation glyph, in points.

    The Hebrew font has no comma or full stop; they are set in the Latin face.
    Using the glyph's own bearing lets the mark sit against the Hebrew word
    instead of on the edge of its monospaced advance.
    """
    global _PUNCT_METRICS
    if _PUNCT_METRICS is None:
        from fontTools.ttLib import TTFont as FTFont
        face = FTFont(mb.pick(mb.LATIN_CANDIDATES, "Latin"))
        _PUNCT_METRICS = (face, face.getBestCmap(), face["head"].unitsPerEm)
    face, cmap, upem = _PUNCT_METRICS
    name = cmap[ord(ch)]
    advance = face["hmtx"][name][0]
    x_max = face["glyf"][name].xMax
    return (advance - x_max) * size / upem


def centred_he(c, x, y, size, text, font="BirdHebrew"):
    c.setFont(font, size)
    c.drawCentredString(x, y, heb(text))


# ---------------------------------------------------------------- geometry

class Metrics:
    """A5 single column; same attribute names as the A4 family layout."""

    def __init__(self, base=10.0):
        self.base = base
        self.row_h = base * 1.62
        self.margin_x = 13 * mm
        self.margin_top = 14 * mm
        self.margin_bot = 15 * mm
        self.cols, self.gutter = 1, 0
        self.genus_size = base * 1.24
        self.family_head_size = base * 1.46
        self.family_size = base * 0.78
        self.block_gap = 3.2 * mm
        self.rule_gap = 1.1 * mm
        self.page_w, self.page_h = 148 * mm, 210 * mm
        self.header_max = 7.6
        self.header_h = 10 * mm
        self.col_top = self.page_h - self.margin_top - self.header_h
        self.col_bottom = self.margin_bot
        self.col_w = self.page_w - 2 * self.margin_x
        self.col_x = [self.margin_x]

    @property
    def right(self):
        return self.margin_x + self.col_w


# ---------------------------------------------------------------- grouping

def load(path, order_source=None):
    """Load records and group them; when given, restore the source's order.

    The final dataset is alphabetised, but ``israel_birds_merged.json`` keeps
    the sequence of the source checklist (Clements 2022): families are yielded
    in taxonomic order and each family knows its order.
    """
    records = json.load(open(path, encoding="utf-8"))
    records = [r for r in records if r.get("latin")]
    families = mf.group_by_family(records)

    fam_order = {}
    for r in records:
        fam_order.setdefault(r["family"], r.get("order", ""))
    for fam in families:
        fam["order"] = fam_order.get(fam["family"], "")

    if order_source and os.path.exists(order_source):
        raw = json.load(open(order_source, encoding="utf-8"))
        rank = {}
        for r in raw:
            rank.setdefault(r["family"], len(rank))
        families.sort(key=lambda f: (rank.get(f["family"], 10 ** 6),
                                     f["family"]))
    return records, families


# ---------------------------------------------------------------- pagination

def paginate_body(m, families):
    """Flow families down one A5 column.

    A family heading never stands alone; when a family continues on a new page
    its heading is repeated with "continued".  Returns pages, the first page of
    every family, and the page of every species row.
    """
    pages, cur = [], []
    y, cur_fam, cur_order = m.col_top, None, None
    fam_page, species_page = {}, {}
    hh = mf.family_head_height(m)

    def flush():
        nonlocal cur, y, cur_fam
        if cur:
            pages.append(cur)
        cur, y, cur_fam = [], m.col_top, None

    for fam in families:
        new_order = fam.get("order", "") != cur_order
        started = False
        for blk in fam["blocks"]:
            need_head = cur_fam != fam["family"]
            extra = ORDER_H if (new_order and not started) else 0.0
            h = mf.block_height(m, blk) + (hh if need_head else 0.0) + extra
            if cur and y - h < m.col_bottom:
                flush()
                need_head = True
                h = mf.block_height(m, blk) + hh + extra
            if extra:
                cur.append(("order", fam.get("order", "")))
                y -= ORDER_H
                cur_order = fam.get("order", "")
            if need_head:
                cur.append(("family", (fam["family"], fam.get("family_he", ""),
                                       started)))
                y -= hh
                cur_fam = fam["family"]
                started = True
                fam_page.setdefault(fam["family"], len(pages) + 1)
            cur.append(("genus", blk))
            y -= mf.block_height(m, blk)
            for sp in blk["species"]:
                species_page.setdefault(sp["latin"], len(pages) + 1)
    flush()
    return pages, fam_page, species_page


def flow1(items, cap, height):
    """Single-column flow that never orphans a heading."""
    pages, cur, used, theme = [], [], 0.0, None
    for item in items:
        h = height(item)
        if cur and used + h > cap + 0.01:
            carry = None
            if cur[-1][0] == "theme":
                carry = cur.pop()
                used -= height(carry)
            pages.append(cur)
            cur, used = [], 0.0
            if carry:
                cur.append(carry)
                used += height(carry)
                theme = carry[1]
            elif item[0] == "entry" and theme is not None:
                cur.append(("theme", f"{theme} ({T['labels.continued']})"))
                used += height(("theme", theme))
        if item[0] == "theme":
            theme = item[1]
        cur.append(item)
        used += h
    if cur:
        pages.append(cur)
    return pages


def flow2(items, cap, height):
    """Two-column flow, repeating the section heading on a new column/page."""
    pages, page = [], [[], []]
    col, used, head = 0, 0.0, None
    for item in items:
        h = height(item)
        if page[col] and used + h > cap + 0.01:
            carry = None
            if page[col][-1][0] == "letter":
                carry = page[col].pop()
                used -= height(carry)
            if col == 0:
                col, used = 1, 0.0
            else:
                pages.append(page)
                page, col, used = [[], []], 0, 0.0
            if carry:
                page[col].append(carry)
                used += height(carry)
                head = carry[1]
            elif item[0] == "entry" and head is not None:
                page[col].append(("letter", head))
                used += height(("letter", head))
        if item[0] == "letter":
            head = item[1]
        page[col].append(item)
        used += h
    if page[0] or page[1]:
        pages.append(page)
    return pages


# ---------------------------------------------------------------- etymology index

def etym_items(etym):
    rows = etym.form_rows()
    items = []
    for theme in etym.themes:
        group = sorted((r for r in rows if r["theme"] == theme),
                       key=lambda r: (r["key"], r["shown"]))
        if not group:
            continue
        items.append(("theme", theme))
        items += [("entry", (r["shown"], r["en"], r["he"])) for r in group]
    return items


def etym_height(item):
    return ETYM_THEME if item[0] == "theme" else ETYM_ROW


# ---------------------------------------------------------------- Hebrew index

HEB_ORDER = "אבגדהוזחטיכלמנסעפצקרשת"
FINAL = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})


def heb_key(s):
    """Dictionary order: word by word, letters only, final forms normalised.

    Splitting on spaces matters: it files 'שחף' before 'שחפית', rather than
    letting the first letter of the second word decide the order.
    """
    s = s.translate(FINAL)
    words = [wd for wd in s.replace("־", " ").replace("-", " ").split() if wd]
    return tuple(tuple(HEB_ORDER.index(ch) if ch in HEB_ORDER else 99
                       for ch in wd) for wd in words)


def heb_letter(s):
    s = s.translate(FINAL)
    for ch in s:
        if ch in HEB_ORDER:
            return ch
    return "?"


def hebrew_items(records, species_page):
    by_name = {}
    for sp in records:
        name = (sp.get("hebrew") or "").strip()
        page = species_page.get(sp["latin"])
        if name and page:
            by_name.setdefault(name, set()).add(page)
    names = sorted(by_name, key=lambda s: (heb_key(s), s))
    items, letter = [], None
    for name in names:
        first = heb_letter(name)
        if first != letter:
            items.append(("letter", first))
            letter = first
        refs = ", ".join(str(p) for p in sorted(by_name[name]))
        items.append(("entry", (name, refs)))
    return items


def heb_height(item):
    return HEB_LETTER if item[0] == "letter" else HEB_ROW


# ---------------------------------------------------------------- page furniture

def draw_folio(c, m, pno):
    c.setFillColor(ACCENT)
    c.setFont("BirdLatin", 7.8)
    c.drawCentredString(m.page_w / 2, 7 * mm, str(pno))


def page_families(page):
    out = []
    for kind, val in page:
        if kind == "order":
            continue
        fam = val[0] if kind == "family" else val["family"]
        if fam not in out:
            out.append(fam)
    return out


def draw_body_header(c, m, page, pno):
    top = m.page_h - m.margin_top
    names = " · ".join(page_families(page))
    size = m.header_max
    avail = m.col_w
    while size > 6.0 and w(names, "BirdLatin", size) > avail:
        size -= 0.2
    c.setFillColor(INK)
    c.setFont("BirdLatin", size)
    c.drawString(m.margin_x, top - m.header_max, names)
    c.setStrokeColor(ACCENT_RULE)
    c.setLineWidth(0.5)
    c.line(m.margin_x, m.col_top + 1.8 * mm, m.right, m.col_top + 1.8 * mm)


def latin_width(etym, latin, size):
    return etym.latin_width(latin, size) if etym is not None else w(latin, "BirdLatin", size)


def marker_text(sp):
    mk = (sp.get("status") or "").strip()
    return f"({mk})" if mk else ""


def marker_width(sp, base_size):
    text = marker_text(sp)
    return w(text, "BirdLatin", base_size * MARK_RATIO) if text else 0.0


def pocket_latin_size(m, sp, etym):
    """Latin size for one row: shrink only if the name would enter the column."""
    limit = EN_COL - FIELD_GAP
    widest = latin_width(etym, sp["latin"], m.base)
    if widest <= limit:
        return m.base
    return max(m.base * 0.70, m.base * limit / widest)


def pocket_english_size(m, sp, heb_size):
    """English size for one row, reduced only if it would reach the marker."""
    hw = (w(sp["hebrew"], "BirdHebrew", heb_size, rtl=True)
          if sp["hebrew"] else 3 * mm)
    avail = (m.col_w - EN_COL - FIELD_GAP - marker_width(sp, m.base)
             - MARK_GAP - hw)
    desired = m.base * EN_RATIO
    need = w(sp["english"], "BirdLatin", desired)
    if need and avail < need:
        desired = max(m.base * EN_RATIO * 0.90, desired * avail / need)
    return desired


def draw_pocket_genus_block(c, m, blk, x_left, top, etym):
    """Genus heading, then Latin | English | Hebrew on one row per species.

    The English column is fixed, so the three fields line up from row to row.
    Hebrew names are all right-aligned on the same edge; a marker hangs to the
    left of the name in parentheses, the way a dash hangs in the element index.
    """
    right = x_left + m.col_w
    heb_size = m.base * HE_RATIO
    mark_size = m.base * MARK_RATIO
    x_en = x_left + EN_COL

    c.setFillColor(INK)
    c.setFont("BirdLatin", m.genus_size)
    if etym is not None:
        etym.draw_latin(c, x_left, top - m.genus_size * 0.88,
                        m.genus_size, blk["genus"])
    else:
        c.drawString(x_left, top - m.genus_size * 0.88, blk["genus"])

    rule_y = top - m.genus_size * 1.05 - m.rule_gap * 0.5
    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.7)
    c.line(x_left, rule_y, right, rule_y)

    n = len(blk["species"])
    for i, sp in enumerate(blk["species"]):
        slot_top = rule_y - i * m.row_h
        latin_size = pocket_latin_size(m, sp, etym)
        baseline = slot_top - m.row_h / 2 - max(latin_size, heb_size) * 0.34

        c.setFillColor(INK)
        c.setFont("BirdLatin", latin_size)
        if etym is not None:
            etym.draw_latin(c, x_left, baseline, latin_size, sp["latin"])
        else:
            c.drawString(x_left, baseline, sp["latin"])

        c.setFillColor(QUIET)
        c.setFont("BirdLatin", pocket_english_size(m, sp, heb_size))
        c.drawString(x_en, baseline, sp["english"])

        if sp["hebrew"]:
            name_w = w(sp["hebrew"], "BirdHebrew", heb_size, rtl=True)
            c.setFillColor(INK)
            c.setFont("BirdHebrew", heb_size)
            c.drawRightString(right, baseline, heb(sp["hebrew"]))
        else:
            name_w = w("—", "BirdLatin", latin_size)
            c.setFillColor(FAINT)
            c.setFont("BirdLatin", latin_size)
            c.drawRightString(right, baseline, "—")

        text = marker_text(sp)
        if text:
            c.setFillColor(FAINT)
            c.setFont("BirdLatin", mark_size)
            c.drawRightString(right - name_w - MARK_GAP, baseline, text)

        if i < n - 1:
            c.setStrokeColor(LIGHT_RULE)
            c.setLineWidth(0.4)
            c.line(x_left, slot_top - m.row_h, right, slot_top - m.row_h)

    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.7)
    c.line(x_left, rule_y - n * m.row_h, right, rule_y - n * m.row_h)


def draw_order_heading(c, m, order, top):
    size = 8.2
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", size)
    c.drawString(m.margin_x, top - size * 0.9, order.upper())


def draw_family_heading(c, m, fam, fam_he, top, continued):
    size = m.family_head_size
    baseline = top - size * 0.92
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", size)
    c.drawString(m.margin_x, baseline, fam)
    if continued:
        x = m.margin_x + w(fam, "BirdLatinBold", size) + 2.5 * mm
        c.setFillColor(GREY)
        c.setFont("BirdLatin", size * 0.52)
        c.drawString(x, baseline, T["labels.continued"])
    if fam_he:
        c.setFillColor(INK)
        c.setFont("BirdHebrewBold", size * 0.92)
        c.drawRightString(m.right, baseline, heb(fam_he))
    rule_y = top - size * 1.4
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.2)
    c.line(m.margin_x, rule_y, m.right, rule_y)
    return rule_y


# ---------------------------------------------------------------- front matter

def draw_title_page(c, m):
    lw = 46 * mm
    lh = lw * 1705 / 1779
    c.drawImage(LOGO, (m.page_w - lw) / 2, 138 * mm, lw, lh, mask="auto")

    c.setFillColor(INK)
    centred_he(c, m.page_w / 2, 116 * mm, 26, TITLE_HE, "BirdHebrewBold")
    centred_he(c, m.page_w / 2, 103 * mm, 11.5, SUBTITLE_HE)

    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.0)
    c.line(54 * mm, 95 * mm, 94 * mm, 95 * mm)

    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 16)
    c.drawCentredString(m.page_w / 2, 83 * mm, TITLE_EN)
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 9)
    c.drawCentredString(m.page_w / 2, 74.5 * mm, SUBTITLE_EN)

    c.setFillColor(INK)
    c.setFont("BirdLatin", 10.5)
    c.drawCentredString(m.page_w / 2, 55 * mm, AUTHOR)
    c.setFillColor(GREY)
    c.setFont("BirdLatin", 8.5)
    c.drawCentredString(m.page_w / 2, 45 * mm, EDITION)


def draw_copyright_page(c, m):
    x, right = m.margin_x, m.right
    y = m.page_h - 38 * mm
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 12)
    c.drawString(x, y, TITLE_EN)
    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 12)
    c.drawRightString(right, y, heb(TITLE_HE))

    y -= 15
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 9)
    c.drawString(x, y, SUBTITLE_EN)
    y -= 14
    c.drawString(x, y, EDITION)

    y -= 26
    c.setFillColor(INK)
    c.setFont("BirdLatin", 9)
    c.drawString(x, y, T["copyright.rights"])

    y -= 16
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 8.5)
    c.drawString(x, y, f"Logo: {T['book.logo_credit']}")

    y -= 26
    paras = [
        T["copyright.sources_1"],
        T["copyright.sources_2"],
        T["copyright.disclaimer"],
    ]
    for para in paras:
        c.setFillColor(QUIET)
        c.setFont("BirdLatin", 8.2)
        for line in wrap_words(para, "BirdLatin", 8.2, m.col_w):
            c.drawString(x, y, line)
            y -= 11.5
        y -= 7

    y -= 10
    c.setStrokeColor(ACCENT_RULE)
    c.setLineWidth(0.5)
    c.line(x, y, right, y)

    y -= 14
    c.setFillColor(INK)
    c.setFont("BirdLatin", 9)
    c.drawString(x, y, T["copyright.printed_en"])
    c.setFont("BirdHebrew", 9)
    c.drawRightString(right, y, heb(T["copyright.printed_he"]))

    y -= 14
    c.setFillColor(FAINT)
    c.setFont("BirdLatin", 7.4)
    c.drawString(x, y, T["copyright.typeset"])


def draw_dedication_page(c, m):
    """Two lines, as written: the name and its comma, then the dedication."""
    size = 14.0
    line1 = T["dedication.line1"]
    word = line1[:-1].rstrip() if line1.endswith(",") else line1
    comma = "," if line1.endswith(",") else ""
    hw = w(word, "BirdHebrew", size, rtl=True)
    # Top-right, both lines ending on the right margin, at normal leading.
    y = m.page_h - m.margin_top - 12 * mm
    word_left = m.right - hw

    c.setFillColor(INK)
    c.setFont("BirdHebrew", size)
    c.drawRightString(m.right, y, heb(word))
    if comma:
        c.setFont("BirdLatin", size)
        c.drawRightString(word_left + punct_rsb(comma, size), y, comma)

    line2 = T["dedication.line2"]
    full_stop = line2[-1] if line2.endswith(".") else ""
    body2 = line2[:-1].rstrip() if full_stop else line2
    hw2 = w(body2, "BirdHebrew", size, rtl=True)
    y2 = y - size * 1.5

    c.setFont("BirdHebrew", size)
    c.drawRightString(m.right, y2, heb(body2))
    if full_stop:
        c.setFont("BirdLatin", size)
        c.drawRightString(m.right - hw2 + punct_rsb(full_stop, size),
                          y2, full_stop)


def draw_contents_page(c, m, families, fam_page, sect):
    families = sorted(families, key=lambda f: f["family"])
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 16)
    c.drawString(m.margin_x, top - 16, T["contents.heading_en"])
    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 14)
    c.drawRightString(m.right, top - 16, heb(T["contents.heading_he"]))

    y = top - 42
    sections = [
        (T["contents.section_list"], 1),
        (T["contents.section_hebrew"], sect["hebrew"]),
        (T["contents.section_elements"], sect["etym"]),
    ]
    for name, pno in sections:
        c.setFillColor(INK)
        c.setFont("BirdLatin", 9.2)
        c.drawString(m.margin_x, y, name)
        c.setFillColor(ACCENT)
        c.setFont("BirdLatin", 9.2)
        c.drawRightString(m.right, y, str(pno))
        y -= 15

    y -= 6
    c.setStrokeColor(ACCENT_RULE)
    c.setLineWidth(0.6)
    c.line(m.margin_x, y, m.right, y)
    y -= 16

    ncol, gap = 3, 5 * mm
    col_w = (m.col_w - gap * (ncol - 1)) / ncol
    per_col = math.ceil(len(families) / ncol)
    row_h = 5.0 * mm

    for ci in range(ncol):
        x = m.margin_x + ci * (col_w + gap)
        yy = y
        c.setFillColor(FAINT)
        c.setFont("BirdLatin", 6.4)
        c.drawString(x, yy, T["contents.column_family"])
        c.drawRightString(x + col_w, yy, T["contents.column_page"])
        yy -= 10
        c.setStrokeColor(LIGHT_RULE)
        c.setLineWidth(0.4)
        c.line(x, yy + 3, x + col_w, yy + 3)
        yy -= 5
        for fam in families[ci * per_col:(ci + 1) * per_col]:
            c.setFillColor(INK)
            c.setFont("BirdLatin", 8.4)
            c.drawString(x, yy, fam["family"])
            c.setFillColor(ACCENT)
            c.setFont("BirdLatin", 8.4)
            c.drawRightString(x + col_w, yy, str(fam_page[fam["family"]]))
            yy -= row_h


def draw_key_page(c, m, etym):
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 16)
    c.drawString(m.margin_x, top - 16, T["key.heading_en"])
    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 12)
    c.drawRightString(m.right, top - 16, heb(T["key.heading_he"]))

    y = top - 42
    size = 9.0
    paras = [T["key.intro_1"], T["key.intro_2"]]
    for para in paras:
        c.setFillColor(QUIET)
        c.setFont("BirdLatin", size)
        for line in wrap_words(para, "BirdLatin", size, m.col_w):
            c.drawString(m.margin_x, y, line)
            y -= size * 1.45
        y -= 7

    y -= 4
    x0 = m.margin_x + 8 * mm
    if etym is not None:
        etym.draw_latin(c, x0, y - 2, 12, T["key.example_latin"])
    c.setFillColor(GREY)
    c.setFont("BirdLatin", 8.2)
    c.drawString(x0, y - 18, T["key.example_gloss"])

    y -= 40
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", size)
    c.drawString(m.margin_x, y, T["key.markers_intro"])
    y -= size * 1.8

    marker_w = 17 * mm
    body_w = m.col_w - marker_w
    for marker, text in LEGEND_TEXT:
        lines = wrap_words(text, "BirdLatin", 8.6, body_w) or [""]
        shown = f"({marker})" if marker != "—" else "—"
        c.setFillColor(INK)
        c.setFont("BirdLatin", 9)
        c.drawString(m.margin_x, y, shown)
        c.setFillColor(QUIET)
        c.setFont("BirdLatin", 8.6)
        for i, ln in enumerate(lines):
            c.drawString(m.margin_x + marker_w, y - i * 11.5, ln)
        y -= max(1, len(lines)) * 11.5 + 5

    y -= 8
    c.setFillColor(GREY)
    for line in wrap_words(T["key.markers_note"], "BirdLatin", 8.0, m.col_w):
        c.drawString(m.margin_x, y, line)
        y -= 11.5

    y -= 14
    c.setStrokeColor(ACCENT_RULE)
    c.setLineWidth(0.6)
    c.line(m.margin_x, y, m.right, y)

    y -= 14
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 10.5)
    c.drawString(m.margin_x, y, T["key.order_heading_en"])
    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 10)
    c.drawRightString(m.right, y, heb(T["key.order_heading_he"]))

    y -= 13
    for para in [T["key.order_note_1"], T["key.order_note_2"]]:
        c.setFillColor(QUIET)
        c.setFont("BirdLatin", 8.2)
        for line in wrap_words(para, "BirdLatin", 8.2, m.col_w):
            c.drawString(m.margin_x, y, line)
            y -= 11.5
        y -= 5


# ---------------------------------------------------------------- indexes

def draw_etym_page(c, m, items, pno):
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 13)
    c.drawString(m.margin_x, top - 13, T["element_index.heading_en"])
    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 10.5)
    c.drawRightString(m.right, top - 13,
                      heb(T["element_index.heading_he"]))

    y = top - 26
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 7.4)
    sub = T["element_index.subtitle"]
    for line in wrap_words(sub, "BirdLatin", 7.4, m.col_w):
        c.drawString(m.margin_x, y, line)
        y -= 10.5

    y -= 6
    dash_w = w("-", "BirdLatin", 8.8)
    x_text = m.margin_x + dash_w
    x_en = m.margin_x + 92
    x_he = m.right
    c.setFillColor(FAINT)
    c.setFont("BirdLatin", 6.4)
    c.drawString(x_text, y, T["element_index.column_element"])
    c.drawString(x_en, y, T["element_index.column_english"])
    c.drawRightString(x_he, y, T["element_index.column_hebrew"])
    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.5)
    c.line(m.margin_x, y - 4, x_he, y - 4)

    cy = y - 18
    for i, (kind, val) in enumerate(items):
        if kind == "theme":
            cy -= 4
            c.setFillColor(ACCENT)
            c.setFont("BirdLatinBold", 8.4)
            c.drawString(m.margin_x, cy - 8.4, val.upper())
            c.setStrokeColor(ACCENT_RULE)
            c.setLineWidth(0.5)
            c.line(m.margin_x, cy - 12.5, x_he, cy - 12.5)
            cy -= ETYM_THEME - 4
            continue

        elem, en, he = val
        baseline = cy - 7.6
        c.setFillColor(INK)
        c.setFont("BirdLatin", 8.8)
        if elem.startswith("-"):
            c.drawString(m.margin_x, baseline, "-")
            c.drawString(x_text, baseline, elem[1:])
        else:
            c.drawString(x_text, baseline, elem)

        c.setFillColor(QUIET)
        c.setFont("BirdLatin", 8.2)
        c.drawString(x_en, baseline, en)

        c.setFillColor(INK)
        c.setFont("BirdHebrew", 8.8)
        c.drawRightString(x_he, baseline, heb(he))

        cy -= ETYM_ROW
        if i < len(items) - 1 and items[i + 1][0] != "theme":
            c.setStrokeColor(LIGHT_RULE)
            c.setLineWidth(0.3)
            c.line(m.margin_x, cy, x_he, cy)
    draw_folio(c, m, pno)


def draw_hebrew_page(c, m, cols, pno):
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 13)
    c.drawString(m.margin_x, top - 13, T["hebrew_index.heading_en"])
    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 10.5)
    c.drawRightString(m.right, top - 13,
                      heb(T["hebrew_index.heading_he"]))

    y = top - 26
    c.setFillColor(QUIET)
    c.setFont("BirdLatin", 7.4)
    sub = T["hebrew_index.subtitle"]
    for line in wrap_words(sub, "BirdLatin", 7.4, m.col_w):
        c.drawString(m.margin_x, y, line)
        y -= 10.5

    col_w = (m.col_w - 6 * mm) / 2
    # Hebrew reads right-to-left: the first half of the alphabet is the right
    # column, so column 0 is drawn on the right.
    col_x = [m.margin_x + col_w + 6 * mm, m.margin_x]
    y -= 10

    for ci, items in enumerate(cols):
        x, right = col_x[ci], col_x[ci] + col_w
        c.setFillColor(FAINT)
        c.setFont("BirdLatin", 6.4)
        c.drawString(x, y, T["hebrew_index.column_page"])
        c.setFont("BirdHebrew", 6.4)
        c.drawRightString(right, y, heb(T["hebrew_index.column_name"]))
        c.setStrokeColor(MID_RULE)
        c.setLineWidth(0.5)
        c.line(x, y - 4, right, y - 4)

        cy = y - 18
        for item in items:
            kind, val = item
            if kind == "letter":
                cy -= 3
                c.setFillColor(ACCENT)
                c.setFont("BirdHebrewBold", 15)
                c.drawRightString(right, cy - 12, heb(val))
                c.setStrokeColor(ACCENT_RULE)
                c.setLineWidth(0.5)
                c.line(x, cy - 16, right, cy - 16)
                cy -= HEB_LETTER - 3
                continue

            name, refs = val
            baseline = cy - 7.6
            c.setFillColor(ACCENT)
            c.setFont("BirdLatin", 7.8)
            c.drawString(x, baseline, refs)
            c.setFillColor(INK)
            c.setFont("BirdHebrew", 8.8)
            c.drawRightString(right, baseline, heb(name))
            cy -= HEB_ROW

    draw_folio(c, m, pno)


def draw_notes_page(c, m, pno):
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    c.setFont("BirdLatinBold", 13)
    c.drawString(m.margin_x, top - 13, T["notes.heading_en"])
    c.setFillColor(INK)
    c.setFont("BirdHebrewBold", 10.5)
    c.drawRightString(m.right, top - 13, heb(T["notes.heading_he"]))

    y = top - 40
    c.setStrokeColor(LIGHT_RULE)
    c.setLineWidth(0.4)
    for _ in range(NOTES_ROWS):
        c.line(m.margin_x, y, m.right, y)
        y -= 5.6 * mm
    draw_folio(c, m, pno)


# ---------------------------------------------------------------- body

def draw_body_page(c, m, page, pno, etym):
    draw_body_header(c, m, page, pno)
    y = m.col_top
    for kind, val in page:
        if kind == "order":
            draw_order_heading(c, m, val, y)
            y -= ORDER_H
        elif kind == "family":
            draw_family_heading(c, m, val[0], val[1], y, val[2])
            y -= mf.family_head_height(m)
        else:
            draw_pocket_genus_block(c, m, val, m.margin_x, y, etym)
            y -= mf.block_height(m, val)
    draw_folio(c, m, pno)


# ---------------------------------------------------------------- render

def render(args):
    latin_font, hebrew_font = register_fonts()
    m = Metrics(args.base)
    records, families = load(args.data, args.order_source)
    etym = Etymology(args.etym)

    body, fam_page, species_page = paginate_body(m, families)
    n_body = len(body)

    etym_pages = []
    if etym is not None:
        # Capacity must match draw_etym_page: title, subtitle, column header.
        cap = (m.page_h - m.margin_top - 26
               - 21 - 6 - 18) - m.margin_bot
        etym_pages = flow1(etym_items(etym), cap, etym_height)
    n_etym = len(etym_pages)

    hebrew_pages = []
    cap_h = (m.page_h - m.margin_top - 26 - 21 - 10 - 18) - m.margin_bot
    hebrew_pages = flow2(hebrew_items(records, species_page), cap_h, heb_height)
    n_hebrew = len(hebrew_pages)

    sect = {"hebrew": n_body + 1, "etym": n_body + n_hebrew + 1}

    front = 5
    total = front + n_body + n_etym + n_hebrew + 1          # + notes
    pad = (-total) % 4
    total += pad

    out = args.out
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c = canvas.Canvas(out, pagesize=(m.page_w, m.page_h),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle("Birds of Israel — pocket edition")
    c.setAuthor(AUTHOR)
    c.setSubject("Latin names, Hebrew names and etymology for bird ringers")
    c.setCreator("book/make_pocket.py")

    draw_title_page(c, m)
    c.showPage()
    draw_copyright_page(c, m)
    c.showPage()
    draw_dedication_page(c, m)
    c.showPage()
    draw_contents_page(c, m, families, fam_page, sect)
    c.showPage()
    draw_key_page(c, m, etym)
    c.showPage()

    for i, page in enumerate(body, start=1):
        draw_body_page(c, m, page, i, etym)
        c.showPage()

    for i, cols in enumerate(hebrew_pages, start=1):
        draw_hebrew_page(c, m, cols, n_body + i)
        c.showPage()

    for i, items in enumerate(etym_pages, start=1):
        draw_etym_page(c, m, items, n_body + n_hebrew + i)
        c.showPage()

    draw_notes_page(c, m, n_body + n_etym + n_hebrew + 1)
    c.showPage()

    for _ in range(pad):
        c.showPage()

    c.save()

    print(f"Wrote {out}")
    print(f"  A5, base {args.base:g} pt")
    print(f"  front matter 5 + body {n_body} + etymology index {n_etym} "
          f"+ Hebrew index {n_hebrew} + notes 1 + blanks {pad} = {total} pages")
    print(f"  {len(families)} families, {len(records)} species, "
          f"{leaves_for_spine(total):.2f} mm spine at 90 gsm")
    print(f"  Latin font : {latin_font}")
    print(f"  Hebrew font: {hebrew_font}")
    return total


def leaves_for_spine(total_pages):
    """Approximate spine width: sheets x 0.11 mm (90 gsm uncoated)."""
    return (total_pages / 2) * 0.11


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "data",
                                                   "israel_birds_final.json"))
    ap.add_argument("--etym", default=os.path.join(ROOT, "data",
                                                   "etymology.json"))
    ap.add_argument("--order-source", default=os.path.join(ROOT, "data",
                                                           "israel_birds_merged.json"),
                    help="source whose family order defines the taxonomic sequence")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "book",
                                                  "israel_birds_pocket.pdf"))
    ap.add_argument("--base", type=float, default=10.0)
    args = ap.parse_args()
    render(args)


if __name__ == "__main__":
    main()
