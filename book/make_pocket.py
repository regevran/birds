#!/usr/bin/env python3
"""Birds of Israel — A5 pocket edition (perfect-bound softcover).

A separate work from the A4 learning sheets.  All printed prose lives in
``book/text.md``; this file places it.  It reads the same source data
(``data/israel_birds_final.json`` and ``data/etymology.json``) but has its own
layout, front matter, monochrome palette and indexes:

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
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from bidi.algorithm import get_display
from reportlab.lib.colors import CMYKColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

import book_text
import make_book as mb
import make_book_family as mf
import pocket_fonts
from make_book import hebrew_text, w
from etym import Etymology

# ---------------------------------------------------------------- identity

TEXT_PATH = os.path.join(ROOT, "book", "text.md")
T = book_text.Text(TEXT_PATH)

TITLE_HE = T["book.title_he"]
SUBTITLE_HE = T["book.subtitle_he"]
EDITION_HE = T["book.edition_he"]
AUTHOR_HE = T["book.author_he"]
AUTHOR = T["book.author"]

LEGEND_TEXT = [
    ("A", T["key.legend_a"]),
    ("I", T["key.legend_i"]),
    ("Ex", T["key.legend_ex"]),
    ("X", T["key.legend_x"]),
]

KEY_INDEXES = [
    ("α", "key.index_hebrew_species"),
    ("η", "key.index_english_species"),
    ("φ", "key.index_latin_families"),
    ("μ", "key.index_hebrew_families"),
    ("λ", "key.index_latin_species"),
    ("ρ", "key.index_elements"),
]

LOGO = os.path.join(ROOT, "book", "assets", "logo_circle_gray.png")


def K(level):
    """K-only print colour (C=M=Y=0); the interior is printed B/W."""
    return CMYKColor(0, 0, 0, level)


# The interior is monochrome; the cover keeps the warm colour palette.
ACCENT = K(1.00)         # headings, family names, folios
ACCENT_RULE = K(0.45)    # section rules
INK = K(1.00)            # body text
QUIET = K(0.75)          # English names, secondary text
GREY = K(0.70)           # continuation labels, explanatory notes
FAINT = K(0.60)          # small labels and markers
LIGHT_RULE = K(0.35)     # row separators
MID_RULE = K(0.55)       # genus and header rules

# Index metrics (points).
ETYM_ROW, ETYM_THEME = 10.8, 26.0
ETYM_VAR = 8.5
ETYM_EN_X = 80                 # points from the text edge to the second column
HEB_ROW, HEB_LETTER = 10.8, 20.0
HEB_TOP_INSET = 32          # points from the top margin to the first column
HEB_COLUMNS = 3             # established for index pages where the width fits
ENG_ROW, ENG_LETTER = 10.4, 20.0
ENG_COLUMNS = 2             # long English names do not fit three columns

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


# Mixed Hebrew/Latin prose is drawn in per-script font runs (see mixed_text).
from mixed_text import (draw_left_para, draw_rich, draw_rich_para,
                        rich_width, wrap_rich)


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
    its heading is repeated.  Returns pages, the first page of every family,
    and the page of every species row.
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
                cur.append(("theme", theme))
                used += height(("theme", theme))
        if item[0] == "theme":
            theme = item[1]
        cur.append(item)
        used += h
    if cur:
        pages.append(cur)
    return pages


def flow2(items, cap, height, ncols=2):
    """N-column flow, repeating the section heading on a new column/page."""
    pages, page = [], [[] for _ in range(ncols)]
    col, used, head = 0, 0.0, None
    for item in items:
        h = height(item)
        if page[col] and used + h > cap + 0.01:
            carry = None
            if page[col][-1][0] == "letter":
                carry = page[col].pop()
                used -= height(carry)
            if col < ncols - 1:
                col, used = col + 1, 0.0
            else:
                pages.append(page)
                page, col, used = [[] for _ in range(ncols)], 0, 0.0
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
    if any(page):
        pages.append(page)
    return pages


# ---------------------------------------------------------------- etymology index

def etym_items(etym, sort_hebrew=True):
    rows = etym.form_rows()
    by_meaning = defaultdict(list)
    for row in rows:
        by_meaning[(row["theme"], row["he"])].append(row)

    items = []
    for theme in etym.themes:
        group = [r for r in rows if r["theme"] == theme]
        if sort_hebrew:
            group.sort(key=lambda r: (heb_key(r["he"]), r["key"], r["shown"]))
        else:
            group.sort(key=lambda r: (r["key"], r["shown"]))
        if not group:
            continue
        items.append(("theme", T["themes." + theme]))
        for row in group:
            variants = sorted(
                (r["shown"] for r in by_meaning[(row["theme"], row["he"])]
                 if r["key"] != row["key"]),
                key=lambda s: (s.lstrip("-").lower(), s))
            line = " ".join(variants) if variants else ""
            items.append(("entry", (row["shown"], row["en"], row["he"],
                                    line)))
    return items


def etym_var_width():
    """Width available to a variant line, from the element column."""
    return 122 * mm - w("-", "BirdLatin", 8.8)


def etym_height(item):
    if item[0] == "theme":
        return ETYM_THEME
    line = item[1][3]
    if not line:
        return ETYM_ROW
    return ETYM_ROW + len(wrap_rich(line, 6.8, etym_var_width())) * ETYM_VAR


def etym_capacity(m):
    """Usable height below the title and column header on a themed page."""
    return (m.page_h - m.margin_top - 32 - 18) - m.margin_bot


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


# ---------------------------------------------------------------- English index

def english_key(s):
    """Dictionary order: word by word, ignoring case and punctuation."""
    return tuple(re.findall(r"[a-z0-9]+", s.lower()))


def english_items(records, species_page):
    by_name = {}
    for sp in records:
        name = (sp.get("english") or "").strip()
        page = species_page.get(sp["latin"])
        if name and page:
            by_name.setdefault(name, set()).add(page)

    names = sorted(by_name, key=lambda s: (english_key(s), s))
    items, letter = [], None
    for name in names:
        first = name[0].upper()
        if first != letter:
            items.append(("letter", first))
            letter = first
        refs = ", ".join(str(p) for p in sorted(by_name[name]))
        items.append(("entry", (name, refs)))
    return items


def eng_height(item):
    return ENG_LETTER if item[0] == "letter" else ENG_ROW


def latin_letter_bounds(cols):
    """The first and last A–Z headings shown on an English index page."""
    letters = []
    for col in cols:
        for kind, val in col:
            if kind == "letter":
                letters.append(val)
    if not letters:
        return None
    letters = sorted(set(letters))
    return letters[0], letters[-1]


def latin_letter_range(cols):
    """The first–last A–Z headings, as one label."""
    bounds = latin_letter_bounds(cols)
    if not bounds:
        return ""
    a, b = bounds
    return a if a == b else f"{a}–{b}"


# ---------------------------------------------------------------- family indexes

def latin_family_items(families, fam_page):
    items, letter = [], None
    for fam in sorted(families, key=lambda f: f["family"]):
        page = fam_page.get(fam["family"])
        if not page:
            continue
        first = fam["family"][0].upper()
        if first != letter:
            items.append(("letter", first))
            letter = first
        items.append(("entry", (fam["family"], str(page))))
    return items


def hebrew_family_items(families, fam_page):
    by_name = {}
    for fam in families:
        name = (fam.get("family_he") or "").strip()
        page = fam_page.get(fam["family"])
        if name and page:
            by_name.setdefault(name, set()).add(page)

    items, letter = [], None
    for name in sorted(by_name, key=lambda s: (heb_key(s), s)):
        first = heb_letter(name)
        if first != letter:
            items.append(("letter", first))
            letter = first
        refs = ", ".join(str(p) for p in sorted(by_name[name]))
        items.append(("entry", (name, refs)))
    return items


def latin_family_height(item):
    return ENG_LETTER if item[0] == "letter" else ENG_ROW


def hebrew_family_height(item):
    return HEB_LETTER if item[0] == "letter" else HEB_ROW


# ---------------------------------------------------------------- Latin species

def latin_species_items(records, species_page):
    by_name = {}
    for sp in records:
        name = (sp.get("latin") or "").strip()
        page = species_page.get(name)
        if name and page:
            by_name.setdefault(name, set()).add(page)

    items, letter = [], None
    for name in sorted(by_name, key=lambda s: (s.lower(), s)):
        first = name[0].upper()
        if first != letter:
            items.append(("letter", first))
            letter = first
        refs = ", ".join(str(p) for p in sorted(by_name[name]))
        items.append(("entry", (name, refs)))
    return items


def latin_species_height(item):
    return ENG_LETTER if item[0] == "letter" else ENG_ROW


# ---------------------------------------------------------------- element index

EL_ROW = 10.8
EL_TOP_INSET = 38            # room for the column-title line


def page_ranges(pages):
    """Compact a page set: 12, 16, 19, 20, 21 -> 12, 16, 19–21."""
    pages = sorted(pages)
    out, i = [], 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1:
            j += 1
        out.append(str(pages[i]) if i == j else f"{pages[i]}–{pages[j]}")
        i = j + 1
    return ", ".join(out)


def element_index_items(etym, records, species_page, cap):
    """Alphabetical word-element index: form, theme page, list pages."""
    rows = etym.form_rows()
    shown_to_key = {r["shown"]: r["key"] for r in rows}

    occ = {}
    for sp in records:
        page = species_page.get(sp["latin"])
        if not page:
            continue
        for word in (sp.get("genus", ""), sp.get("epithet", "")):
            for surface, _eid in etym.splits.get(word, []):
                occ.setdefault(surface.lower(), set()).add(page)

    theme_page = {}
    for pno, page_items in enumerate(
            flow1(etym_items(etym), cap, etym_height), start=1):
        for kind, val in page_items:
            if kind == "entry":
                shown = val[0]
                key = shown_to_key.get(shown, shown.strip("-").lower())
                theme_page.setdefault(key, pno)

    items, letter = [], None
    for row in sorted(rows, key=lambda r: (r["key"], r["shown"])):
        key = row["key"]
        first = key[0].upper() if key else "?"
        if first != letter:
            items.append(("letter", first))
            letter = first
        refs = ""
        if occ.get(key):
            refs = page_ranges(occ[key])
        group = T["theme_short." + row["theme"]]
        items.append(("entry", (row["shown"], str(theme_page.get(key, "")),
                                row["he"], group, refs)))
    return items


def element_index_height(item):
    return ENG_LETTER if item[0] == "letter" else EL_ROW


# ---------------------------------------------------------------- page furniture

def draw_folio(c, m, pno):
    c.setFillColor(ACCENT)
    c.setFont("BirdLatin", 7.8)
    c.drawCentredString(m.page_w / 2, 7 * mm, str(pno))


ROMAN = ("", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii")


def draw_roman_folio(c, m, pno):
    c.setFillColor(ACCENT)
    c.setFont("BirdLatin", 7.8)
    c.drawCentredString(m.page_w / 2, 7 * mm, ROMAN[pno])


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

    c.setFillColor(INK)
    draw_rich(c, AUTHOR_HE, 10.5, m.page_w / 2, 76 * mm, align="center")
    c.setFillColor(GREY)
    draw_rich(c, EDITION_HE, 8.5, m.page_w / 2, 65 * mm, align="center")


def draw_copyright_page(c, m):
    x, right = m.margin_x, m.right
    y = m.page_h - 38 * mm
    c.setFillColor(ACCENT)
    draw_rich(c, TITLE_HE, 14, right, y, he_bold=True)

    y -= 16
    c.setFillColor(QUIET)
    draw_rich(c, SUBTITLE_HE, 9, right, y)
    y -= 14
    draw_rich(c, EDITION_HE, 9, right, y)

    y -= 26
    c.setFillColor(INK)
    draw_rich(c, T["copyright.rights"], 9, right, y)

    y -= 16
    c.setFillColor(QUIET)
    logo = f"{T['copyright.logo_label']} {T['book.logo_credit']}"
    draw_rich(c, logo, 8.5, right, y)

    y -= 26
    sources = [
        (T["copyright.sources_1"], T["copyright.sources_1_en"]),
        (T["copyright.sources_2"], T["copyright.sources_2_en"]),
    ]
    for he_para, en_para in sources:
        c.setFillColor(QUIET)
        y = draw_rich_para(c, he_para, 8.2, right, y, m.col_w, leading=11.5)
        y -= 4
        c.setFillColor(GREY)
        y = draw_left_para(c, en_para, 7.6, x, y, m.col_w, leading=10.5)
        y -= 9

    c.setFillColor(QUIET)
    y = draw_rich_para(c, T["copyright.disclaimer"], 8.2, right, y, m.col_w,
                       leading=11.5)
    y -= 7

    y -= 10
    c.setStrokeColor(ACCENT_RULE)
    c.setLineWidth(0.5)
    c.line(x, y, right, y)

    y -= 14
    c.setFillColor(INK)
    draw_rich(c, T["copyright.printed_he"], 9, right, y)

    y -= 14
    c.setFillColor(FAINT)
    draw_rich_para(c, T["copyright.typeset"], 7.4, right, y, m.col_w,
                   leading=10.5)


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


def draw_contents_page(c, m, sections):
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["contents.heading_he"], 16, m.right, top - 16,
              he_bold=True)

    y = top - 42
    for name, pno in sections:
        c.setFillColor(ACCENT)
        c.setFont("BirdLatin", 9.4)
        c.drawString(m.margin_x, y, str(pno))
        c.setFillColor(INK)
        draw_rich(c, name, 9.6, m.right, y)
        y -= 16.5


def draw_key_label(c, m, text, size, x, y):
    """Draw an index label, bolding the first letter of the mnemonic target."""
    plain = text.replace("**", "")
    c.setFillColor(QUIET)
    draw_rich(c, plain, size, x, y)
    if "**" not in text:
        return

    target = plain.rsplit("—", 1)[-1].strip().strip(")(").strip()
    pos = plain.rfind(target)
    if pos < 0 or not target:
        return
    suffix = plain[pos + len(target):]
    width = rich_width(plain, size)
    target_w = rich_width(target, size)
    suffix_w = rich_width(suffix, size)
    first = target[0]

    if "֐" <= first <= "׿":
        target_right = x - width + suffix_w + target_w
        c.setFont("BirdHebrewBold", size)
        c.drawRightString(target_right, y, first)
    else:
        target_left = x - width + suffix_w
        c.setFont("BirdLatinBold", size)
        c.drawString(target_left, y, first)


def draw_key_block(c, m, text, y, size=9.0, leading=12.5,
                   text_color=QUIET, title_color=ACCENT):
    """Draw a key-page block in source order: titles, paragraphs, bullets."""
    entries, mode = [], None
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("כותרת:"):
            entries.append(("title", line[len("כותרת:"):].strip()))
            mode = None
        elif line.startswith("- "):
            entries.append(("bullet", line[2:].strip()))
            mode = "bullet"
        elif mode in ("bullet", "para"):
            kind, value = entries[-1]
            entries[-1] = (kind, f"{value} {line}".strip())
        else:
            entries.append(("para", line))
            mode = "para"

    drawn = False
    for kind, value in entries:
        if kind == "title":
            if drawn:
                y -= 6
            c.setFillColor(title_color)
            draw_rich(c, value, 10.5, m.right, y, he_bold=True)
            y -= 13
            drawn = True
        elif kind == "bullet":
            indent = 5 * mm
            lines = wrap_rich(value, size, m.col_w - indent) or [""]
            c.setFillColor(title_color)
            c.setFont("BirdLatin", 8.0)
            c.drawRightString(m.right, y, "•")
            c.setFillColor(text_color)
            for j, line in enumerate(lines):
                draw_rich(c, line, size, m.right - indent,
                          y - j * leading)
            y -= len(lines) * leading + 1.5
            drawn = True
        else:
            c.setFillColor(text_color)
            y = draw_rich_para(c, value, size, m.right, y, m.col_w,
                               leading=leading)
            y -= 4
            drawn = True
    return y


def draw_key_page(c, m, etym):
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["key.heading_he"], 16, m.right, top - 16, he_bold=True)

    y = top - 42
    size = 9.0
    y = draw_key_block(c, m, T["key.intro_1"], y, size)
    y -= 10
    y = draw_key_block(c, m, T["key.intro_2"], y, size)
    y -= 10

    c.setFillColor(ACCENT)
    draw_rich(c, T["key.markers_heading"], 10.5, m.right, y, he_bold=True)
    y -= 13
    c.setFillColor(QUIET)
    draw_rich(c, T["key.markers_intro"], size, m.right, y)
    y -= size * 1.8

    marker_w = 17 * mm
    body_w = m.col_w - marker_w
    for marker, text in LEGEND_TEXT:
        lines = wrap_rich(text, 8.6, body_w) or [""]
        shown = f"({marker})" if marker != "—" else "—"
        c.setFillColor(INK)
        c.setFont("BirdLatin", 9)
        c.drawRightString(m.right, y, shown)
        c.setFillColor(QUIET)
        for i, ln in enumerate(lines):
            draw_rich(c, ln, 8.6, m.right - marker_w, y - i * 11.5)
        y -= max(1, len(lines)) * 11.5 + 5

    y -= 8
    y = draw_key_block(c, m, T["key.markers_note"], y, 8.0, 11.5,
                       text_color=GREY)

    y -= 16
    c.setFillColor(ACCENT)
    draw_rich(c, T["key.index_heading_he"], 10.5, m.right, y, he_bold=True)

    y -= 12
    y = draw_key_block(c, m, T["key.index_intro"], y, 7.8, 10.6)
    y -= 4
    for greek, key in KEY_INDEXES:
        c.setFillColor(INK)
        c.setFont("BirdLatinBold", 9.2)
        c.drawRightString(m.right, y, greek)
        draw_key_label(c, m, T[key], 8.2, m.right - 7 * mm, y)
        y -= 10.8

    y -= 3


# ---------------------------------------------------------------- indexes

def draw_etym_page(c, m, items, pno):
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["element_data.heading_he"], 13, m.right, top - 13,
              he_bold=True)

    y = top - 32
    dash_w = w("-", "BirdLatin", 8.8)
    x_text = m.margin_x + dash_w
    x_en = m.margin_x + ETYM_EN_X
    x_he = m.right
    c.setFillColor(FAINT)
    draw_rich(c, T["element_data.column_element"], 6.4, m.margin_x, y,
              align="left")
    draw_rich(c, T["element_data.column_english"], 6.4, x_en, y,
              align="left")
    draw_rich(c, T["element_data.column_hebrew"], 6.4, x_he, y)
    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.5)
    c.line(m.margin_x, y - 4, x_he, y - 4)

    cy = y - 18
    for i, (kind, val) in enumerate(items):
        if kind == "theme":
            cy -= 4
            c.setFillColor(ACCENT)
            draw_rich(c, val, 15, x_he, cy - 15, he_bold=True)
            c.setStrokeColor(ACCENT_RULE)
            c.setLineWidth(0.5)
            c.line(m.margin_x, cy - 19, x_he, cy - 19)
            cy -= ETYM_THEME
            continue

        elem, en, he, var_line = val
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

        var_h = 0.0
        if var_line:
            lines = wrap_rich(var_line, 6.8, m.col_w - dash_w)
            c.setFillColor(QUIET)
            for j, line in enumerate(lines):
                draw_rich(c, line, 6.8, x_text,
                          baseline - ETYM_VAR * (j + 1), align="left")
            var_h = len(lines) * ETYM_VAR

        cy -= ETYM_ROW + var_h
        if i < len(items) - 1 and items[i + 1][0] != "theme":
            c.setStrokeColor(LIGHT_RULE)
            c.setLineWidth(0.3)
            c.line(m.margin_x, cy, x_he, cy)
    draw_folio(c, m, pno)


def page_letter_bounds(cols):
    """The first and last Hebrew letter headings shown on this page."""
    letters = []
    for col in cols:
        for kind, val in col:
            if kind == "letter":
                letters.append(val)
    if not letters:
        return None
    order = {ch: i for i, ch in enumerate(HEB_ORDER)}
    letters = sorted(set(letters), key=lambda ch: order.get(ch, 99))
    return letters[0], letters[-1]


def page_letter_range(cols):
    """The first–last Hebrew letter headings, as one label."""
    bounds = page_letter_bounds(cols)
    if not bounds:
        return ""
    a, b = bounds
    return a if a == b else f"{a}־{b}"


def draw_index_marker(c, m, rng, title, greek, slot=0,
                      rng_font="BirdHebrew", rng_rtl=True,
                      title_font="BirdHebrewBold", title_rtl=True,
                      letter_stack=False, letters=None):
    """Running line and edge tab shared by the indexes.

    ``slot`` staggers the marker down the fore-edge: the Hebrew index is slot
    0 (α), the English index slot 1 (η), and so on.  The marker stays 5 mm
    inside the trim so the copy shop's cut cannot eat it.  ``letter_stack``
    puts the page's first and last letters inside the same box, below the
    Greek letter, so one 20 mm slot holds all three.
    """
    y = m.page_h - 9 * mm

    c.setFillColor(INK)
    c.setFont(rng_font, 8.2)
    if rng:
        shown = heb(rng) if rng_rtl else rng
        c.drawString(m.margin_x, y, shown)
        rng_w = w(rng, rng_font, 8.2, rtl=rng_rtl)
    else:
        rng_w = 0.0

    c.setFont(title_font, 8.2)
    shown = heb(title) if title_rtl else title
    c.drawRightString(m.right, y, shown)
    title_w = w(title, title_font, 8.2, rtl=title_rtl)

    x0 = m.margin_x + rng_w + 4 * mm
    x1 = m.right - title_w - 4 * mm
    unit = w(greek + " ", "BirdLatin", 7.6)
    n = int((x1 - x0) / unit) if unit and x1 > x0 else 0
    if n > 0:
        c.setFillColor(K(0.60))
        c.setFont("BirdLatin", 7.6)
        c.drawString(x0, y, " ".join([greek] * n))

    c.setStrokeColor(K(0.40))
    c.setLineWidth(0.4)
    c.line(m.margin_x, y - 2 * mm, m.right, y - 2 * mm)

    tab_x, tab_w = 5 * mm, 4.2 * mm
    box_top = 8 * mm + slot * 20 * mm
    box_h = (19 if (letter_stack and letters) else 14) * mm
    box_y = m.page_h - box_top - box_h
    c.setFillColor(K(1))
    c.rect(tab_x, box_y, tab_w, box_h, stroke=0, fill=1)
    c.setFillColor(K(0))
    c.setFont("BirdLatin", 9)
    greek_centre = box_y + (15 * mm if (letter_stack and letters)
                            else box_h / 2)
    c.drawCentredString(tab_x + tab_w / 2, greek_centre - 3, greek)

    if letter_stack and letters:
        first, last = letters
        c.setFont(rng_font, 7.5)
        if first == last:
            shown = heb(first) if rng_rtl else first
            c.drawCentredString(tab_x + tab_w / 2, box_y + 7 * mm - 2.5,
                                shown)
        else:
            for letter, centre in ((first, 9 * mm), (last, 5 * mm)):
                shown = heb(letter) if rng_rtl else letter
                c.drawCentredString(tab_x + tab_w / 2,
                                    box_y + centre - 2.5, shown)


def draw_hebrew_marker(c, m, cols, letter_stack=False):
    """Top line and edge tab for the Hebrew index: range, α, title."""
    draw_index_marker(c, m, page_letter_range(cols),
                      T["hebrew_index.heading_he"], "α",
                      letter_stack=letter_stack,
                      letters=page_letter_bounds(cols))


def draw_hebrew_page(c, m, cols, pno, ncols=2, letter_stack=False):
    draw_hebrew_marker(c, m, cols, letter_stack=letter_stack)
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["hebrew_index.heading_he"], 13, m.right, top - 13,
              he_bold=True)

    # A three-column proof gets slightly tighter gutters than the printed
    # two-column template; the columns themselves are wide enough for the
    # longest name plus its references.
    gutter = (6 if ncols == 2 else 5) * mm
    col_w = (m.col_w - (ncols - 1) * gutter) / ncols
    # Hebrew reads right-to-left: the first column is the rightmost one.
    col_x = [m.margin_x + (ncols - 1 - i) * (col_w + gutter)
             for i in range(ncols)]
    y = top - HEB_TOP_INSET

    for ci, items in enumerate(cols):
        x, right = col_x[ci], col_x[ci] + col_w
        cy = y
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


def draw_english_page(c, m, cols, pno, letter_stack=False):
    draw_index_marker(c, m, latin_letter_range(cols),
                      T["english_index.heading_he"], "η", slot=1,
                      rng_font="BirdLatin", rng_rtl=False,
                      title_font="BirdHebrewBold", title_rtl=True,
                      letter_stack=letter_stack,
                      letters=latin_letter_bounds(cols))
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["english_index.heading_he"], 13, m.right, top - 13,
              he_bold=True)

    gutter = 6 * mm
    col_w = (m.col_w - gutter) / 2
    # English reads left-to-right: the first column is the leftmost one.
    col_x = [m.margin_x, m.margin_x + col_w + gutter]
    y = top - HEB_TOP_INSET

    for ci, items in enumerate(cols):
        x, right = col_x[ci], col_x[ci] + col_w
        cy = y
        for item in items:
            kind, val = item
            if kind == "letter":
                cy -= 3
                c.setFillColor(ACCENT)
                c.setFont("BirdLatinBold", 15)
                c.drawString(x, cy - 12, val)
                c.setStrokeColor(ACCENT_RULE)
                c.setLineWidth(0.5)
                c.line(x, cy - 16, right, cy - 16)
                cy -= ENG_LETTER - 3
                continue

            name, refs = val
            baseline = cy - 7.4
            c.setFillColor(ACCENT)
            c.setFont("BirdLatin", 7.2)
            c.drawRightString(right, baseline, refs)
            c.setFillColor(INK)
            c.setFont("BirdLatin", 8.0)
            c.drawString(x, baseline, name)
            cy -= ENG_ROW

    draw_folio(c, m, pno)


def draw_latin_family_page(c, m, cols, pno, ncols=3, letter_stack=False):
    draw_index_marker(c, m, latin_letter_range(cols),
                      T["latin_family_index.heading_he"], "φ", slot=2,
                      rng_font="BirdLatin", rng_rtl=False,
                      title_font="BirdHebrewBold", title_rtl=True,
                      letter_stack=letter_stack,
                      letters=latin_letter_bounds(cols))
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["latin_family_index.heading_he"], 13, m.right, top - 13,
              he_bold=True)

    gutter = 5 * mm
    col_w = (m.col_w - (ncols - 1) * gutter) / ncols
    col_x = [m.margin_x + i * (col_w + gutter) for i in range(ncols)]
    y = top - HEB_TOP_INSET

    for ci, items in enumerate(cols):
        x, right = col_x[ci], col_x[ci] + col_w
        cy = y
        for item in items:
            kind, val = item
            if kind == "letter":
                cy -= 3
                c.setFillColor(ACCENT)
                c.setFont("BirdLatinBold", 15)
                c.drawString(x, cy - 12, val)
                c.setStrokeColor(ACCENT_RULE)
                c.setLineWidth(0.5)
                c.line(x, cy - 16, right, cy - 16)
                cy -= ENG_LETTER - 3
                continue

            name, refs = val
            baseline = cy - 7.4
            c.setFillColor(ACCENT)
            c.setFont("BirdLatin", 7.4)
            c.drawRightString(right, baseline, refs)
            c.setFillColor(INK)
            c.setFont("BirdLatin", 8.2)
            c.drawString(x, baseline, name)
            cy -= ENG_ROW

    draw_folio(c, m, pno)


def draw_hebrew_family_page(c, m, cols, pno, ncols=3, letter_stack=False):
    draw_index_marker(c, m, page_letter_range(cols),
                      T["hebrew_family_index.heading_he"], "μ", slot=3,
                      title_font="BirdHebrewBold", title_rtl=True,
                      letter_stack=letter_stack,
                      letters=page_letter_bounds(cols))
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["hebrew_family_index.heading_he"], 13, m.right, top - 13,
              he_bold=True)

    gutter = 5 * mm
    col_w = (m.col_w - (ncols - 1) * gutter) / ncols
    col_x = [m.margin_x + (ncols - 1 - i) * (col_w + gutter)
             for i in range(ncols)]
    y = top - HEB_TOP_INSET

    for ci, items in enumerate(cols):
        x, right = col_x[ci], col_x[ci] + col_w
        cy = y
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


def draw_latin_species_page(c, m, cols, pno, ncols=2, letter_stack=False):
    draw_index_marker(c, m, latin_letter_range(cols),
                      T["latin_species_index.heading_he"], "λ", slot=4,
                      rng_font="BirdLatin", rng_rtl=False,
                      title_font="BirdHebrewBold", title_rtl=True,
                      letter_stack=letter_stack,
                      letters=latin_letter_bounds(cols))
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["latin_species_index.heading_he"], 13, m.right, top - 13,
              he_bold=True)

    gutter = 6 * mm
    col_w = (m.col_w - gutter) / 2
    col_x = [m.margin_x, m.margin_x + col_w + gutter]
    y = top - HEB_TOP_INSET

    for ci, items in enumerate(cols):
        x, right = col_x[ci], col_x[ci] + col_w
        cy = y
        for item in items:
            kind, val = item
            if kind == "letter":
                cy -= 3
                c.setFillColor(ACCENT)
                c.setFont("BirdLatinBold", 15)
                c.drawString(x, cy - 12, val)
                c.setStrokeColor(ACCENT_RULE)
                c.setLineWidth(0.5)
                c.line(x, cy - 16, right, cy - 16)
                cy -= ENG_LETTER - 3
                continue

            name, refs = val
            baseline = cy - 7.4
            c.setFillColor(ACCENT)
            c.setFont("BirdLatin", 7.2)
            c.drawRightString(right, baseline, refs)
            c.setFillColor(INK)
            c.setFont("BirdLatin", 8.0)
            c.drawString(x, baseline, name)
            cy -= ENG_ROW

    draw_folio(c, m, pno)


def draw_element_index_page(c, m, cols, pno, ncols=1, letter_stack=False,
                            first_page=False):
    draw_index_marker(c, m, latin_letter_range(cols),
                      T["element_index.heading_he"], "ρ", slot=5,
                      rng_font="BirdLatin", rng_rtl=False,
                      title_font="BirdHebrewBold", title_rtl=True,
                      letter_stack=letter_stack,
                      letters=latin_letter_bounds(cols))
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["element_index.heading_he"], 13, m.right, top - 13,
              he_bold=True)

    x, right = m.margin_x, m.right
    y_head = top - 25
    c.setFillColor(FAINT)
    draw_rich(c, T["element_index.column_latin"], 6.4, x, y_head,
              align="left")
    draw_rich(c, T["element_index.column_page"], 6.4, x + 30 * mm, y_head)
    draw_rich(c, T["element_index.column_meaning"], 6.4, x + 54 * mm,
              y_head)
    draw_rich(c, T["element_index.column_group"], 6.4, x + 66 * mm, y_head)
    draw_rich(c, T["element_index.column_refs"], 6.4, x + 70 * mm, y_head,
              align="left")
    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.5)
    c.line(x, y_head - 4, right, y_head - 4)

    cy = top - EL_TOP_INSET
    for item in cols[0] if cols else []:
        kind, val = item
        if kind == "letter":
            cy -= 3
            c.setFillColor(ACCENT)
            c.setFont("BirdLatinBold", 15)
            c.drawString(x, cy - 12, val)
            c.setStrokeColor(ACCENT_RULE)
            c.setLineWidth(0.5)
            c.line(x, cy - 16, right, cy - 16)
            cy -= ENG_LETTER - 3
            continue

        name, theme, he, group, refs = val
        baseline = cy - 7.6
        dash_w = w("-", "BirdLatin", 8.2)
        letter_x = x + dash_w

        # Hang a leading hyphen; every element's first letter starts on the
        # same edge.
        c.setFillColor(INK)
        c.setFont("BirdLatin", 8.2)
        if name.startswith("-"):
            c.drawString(x, baseline, "-")
            c.drawString(letter_x, baseline, name[1:])
        else:
            c.drawString(letter_x, baseline, name)

        c.setFillColor(ACCENT)
        c.setFont("BirdLatin", 7.8)
        c.drawRightString(x + 30 * mm, baseline, theme)

        c.setFillColor(QUIET)
        draw_rich(c, he, 8.2, x + 54 * mm, baseline)

        c.setFillColor(QUIET)
        draw_rich(c, group, 7.6, x + 66 * mm, baseline)

        if refs:
            ref_w = right - (x + 70 * mm)
            size = 7.8
            while size > 5.5 and w(refs, "BirdLatin", size) > ref_w:
                size -= 0.1
            c.setFillColor(QUIET)
            c.setFont("BirdLatin", size)
            c.drawString(x + 70 * mm, baseline, refs)

        # One fixed row per element: the scanned list never breaks.
        cy -= EL_ROW

    draw_folio(c, m, pno)


def draw_notes_page(c, m, pno):
    top = m.page_h - m.margin_top
    c.setFillColor(ACCENT)
    draw_rich(c, T["notes.heading_he"], 13, m.right, top - 13, he_bold=True)

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
    etym = Etymology(args.etym, part_color=K(0.70), dot_color=K(0.70),
                     plain_color=K(1.00))

    body, fam_page, species_page = paginate_body(m, families)
    n_body = len(body)

    etym_pages = flow1(etym_items(etym), etym_capacity(m), etym_height)
    n_etym = len(etym_pages)
    list_start = n_etym + 1

    shifted = {k: v + (list_start - 1) for k, v in species_page.items()}
    shifted_fam = {k: v + (list_start - 1) for k, v in fam_page.items()}
    cap_h = (m.page_h - m.margin_top - HEB_TOP_INSET) - m.margin_bot

    hebrew_pages = flow2(hebrew_items(records, shifted), cap_h, heb_height,
                         ncols=args.hebrew_columns)
    heb_start = list_start + n_body

    eng_pages = flow2(english_items(records, shifted), cap_h, eng_height,
                      ncols=ENG_COLUMNS)
    eng_start = heb_start + len(hebrew_pages)

    lat_fam_pages = flow2(latin_family_items(families, shifted_fam), cap_h,
                          latin_family_height, ncols=3)
    lat_fam_start = eng_start + len(eng_pages)

    heb_fam_pages = flow2(hebrew_family_items(families, shifted_fam), cap_h,
                          hebrew_family_height, ncols=3)
    heb_fam_start = lat_fam_start + len(lat_fam_pages)

    lat_species_pages = flow2(latin_species_items(records, shifted), cap_h,
                              latin_species_height, ncols=2)
    lat_species_start = heb_fam_start + len(heb_fam_pages)

    el_cap = (m.page_h - m.margin_top - EL_TOP_INSET) - m.margin_bot
    el_items = element_index_items(etym, records, shifted, etym_capacity(m))
    el_pages = flow2(el_items, el_cap, element_index_height, ncols=1)
    el_start = lat_species_start + len(lat_species_pages)

    notes_start = el_start + len(el_pages)
    notes_pages = 2
    tail_blank = 2

    sections = [
        (T["key.heading_he"], "v"),
        (T["element_data.heading_he"], 1),
        (T["contents.section_list"], list_start),
        (T["hebrew_index.heading_he"], heb_start),
        (T["english_index.heading_he"], eng_start),
        (T["latin_family_index.heading_he"], lat_fam_start),
        (T["hebrew_family_index.heading_he"], heb_fam_start),
        (T["latin_species_index.heading_he"], lat_species_start),
        (T["element_index.heading_he"], el_start),
        (T["notes.heading_he"], notes_start),
    ]

    front = 5
    total = front + notes_start + notes_pages - 1 + tail_blank
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
    draw_roman_folio(c, m, 2)
    c.showPage()
    draw_dedication_page(c, m)
    draw_roman_folio(c, m, 3)
    c.showPage()
    draw_contents_page(c, m, sections)
    draw_roman_folio(c, m, 4)
    c.showPage()
    draw_key_page(c, m, etym)
    draw_roman_folio(c, m, 5)
    c.showPage()

    for i, items in enumerate(etym_pages, start=1):
        draw_etym_page(c, m, items, i)
        c.showPage()

    for i, page in enumerate(body, start=list_start):
        draw_body_page(c, m, page, i, etym)
        c.showPage()

    for i, cols in enumerate(hebrew_pages):
        draw_hebrew_page(c, m, cols, heb_start + i,
                         ncols=args.hebrew_columns, letter_stack=True)
        c.showPage()

    for i, cols in enumerate(eng_pages):
        draw_english_page(c, m, cols, eng_start + i, letter_stack=True)
        c.showPage()

    for i, cols in enumerate(lat_fam_pages):
        draw_latin_family_page(c, m, cols, lat_fam_start + i,
                               letter_stack=True)
        c.showPage()

    for i, cols in enumerate(heb_fam_pages):
        draw_hebrew_family_page(c, m, cols, heb_fam_start + i,
                                letter_stack=True)
        c.showPage()

    for i, cols in enumerate(lat_species_pages):
        draw_latin_species_page(c, m, cols, lat_species_start + i,
                                letter_stack=True)
        c.showPage()

    for i, cols in enumerate(el_pages):
        draw_element_index_page(c, m, cols, el_start + i,
                                letter_stack=True, first_page=(i == 0))
        c.showPage()

    for i in range(notes_pages):
        draw_notes_page(c, m, notes_start + i)
        c.showPage()

    for _ in range(tail_blank + pad):
        c.showPage()

    c.save()

    print(f"Wrote {out}")
    print(f"  A5, base {args.base:g} pt")
    print(f"  front matter 5 + themed {n_etym} + body {n_body} "
          f"+ Hebrew {len(hebrew_pages)} + English {len(eng_pages)} "
          f"+ Latin families {len(lat_fam_pages)} "
          f"+ Hebrew families {len(heb_fam_pages)} "
          f"+ Latin species {len(lat_species_pages)} "
          f"+ elements {len(el_pages)} + notes {notes_pages} "
          f"+ blanks {tail_blank + pad} = {total} pages")
    print(f"  {len(families)} families, {len(records)} species, "
          f"{leaves_for_spine(total):.2f} mm spine at 90 gsm")
    print(f"  Latin font : {latin_font}")
    print(f"  Hebrew font: {hebrew_font}")
    return total


def render_hebrew_preview(args):
    """Proof of the Hebrew index in the new structure.

    Themed word elements come first (Arabic 1–11), then the species list
    (12–57), so the index folios and its page references already use their
    final numbers even though only the index is written out.
    """
    register_fonts()
    m = Metrics(args.base)
    records, families = load(args.data, args.order_source)
    etym = Etymology(args.etym, part_color=K(0.70), dot_color=K(0.70),
                     plain_color=K(1.00))

    body, _fam_page, species_page = paginate_body(m, families)
    n_body = len(body)

    cap = etym_capacity(m)
    n_etym = len(flow1(etym_items(etym), cap, etym_height))
    list_start = n_etym + 1
    heb_start = list_start + n_body

    shifted = {k: v + (list_start - 1) for k, v in species_page.items()}
    cap_h = (m.page_h - m.margin_top - HEB_TOP_INSET) - m.margin_bot
    ncols = args.hebrew_columns
    hebrew_pages = flow2(hebrew_items(records, shifted), cap_h, heb_height,
                         ncols=ncols)

    name = "preview-hebrew.pdf" if ncols == 2 else f"preview-hebrew-{ncols}col.pdf"
    out = os.path.join(os.path.dirname(args.out), name)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c = canvas.Canvas(out, pagesize=(m.page_w, m.page_h),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle(f"Birds of Israel — Hebrew index {ncols}-column preview")
    c.setAuthor(AUTHOR)
    c.setCreator("book/make_pocket.py --preview-hebrew")

    for i, cols in enumerate(hebrew_pages):
        draw_hebrew_page(c, m, cols, heb_start + i, ncols=ncols,
                         letter_stack=True)
        c.showPage()
    c.save()

    last = heb_start + len(hebrew_pages) - 1
    print(f"Wrote {out}")
    print(f"  Hebrew index, {ncols} columns: {len(hebrew_pages)} pages, "
          f"folios {heb_start}–{last}")
    print(f"  References point to list pages {list_start}–"
          f"{list_start + n_body - 1}")


def render_english_preview(args):
    """Proof of the English name index, two columns, after the Hebrew one."""
    register_fonts()
    m = Metrics(args.base)
    records, families = load(args.data, args.order_source)
    etym = Etymology(args.etym, part_color=K(0.70), dot_color=K(0.70),
                     plain_color=K(1.00))

    body, _fam_page, species_page = paginate_body(m, families)
    n_body = len(body)

    cap = etym_capacity(m)
    n_etym = len(flow1(etym_items(etym), cap, etym_height))
    list_start = n_etym + 1
    heb_start = list_start + n_body

    shifted = {k: v + (list_start - 1) for k, v in species_page.items()}
    cap_h = (m.page_h - m.margin_top - HEB_TOP_INSET) - m.margin_bot
    hebrew_pages = flow2(hebrew_items(records, shifted), cap_h, heb_height,
                         ncols=args.hebrew_columns)
    eng_start = heb_start + len(hebrew_pages)

    eng_pages = flow2(english_items(records, shifted), cap_h, eng_height,
                      ncols=ENG_COLUMNS)

    out = os.path.join(os.path.dirname(args.out), "preview-english.pdf")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c = canvas.Canvas(out, pagesize=(m.page_w, m.page_h),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle("Birds of Israel — English index preview")
    c.setAuthor(AUTHOR)
    c.setCreator("book/make_pocket.py --preview-english")

    for i, cols in enumerate(eng_pages):
        draw_english_page(c, m, cols, eng_start + i, letter_stack=True)
        c.showPage()
    c.save()

    last = eng_start + len(eng_pages) - 1
    print(f"Wrote {out}")
    print(f"  English index, {ENG_COLUMNS} columns: {len(eng_pages)} pages, "
          f"folios {eng_start}–{last}")
    print(f"  References point to list pages {list_start}–"
          f"{list_start + n_body - 1}")


def render_families_preview(args):
    """Proof of the two separate family indexes: Latin then Hebrew."""
    register_fonts()
    m = Metrics(args.base)
    records, families = load(args.data, args.order_source)
    etym = Etymology(args.etym, part_color=K(0.70), dot_color=K(0.70),
                     plain_color=K(1.00))

    body, fam_page, species_page = paginate_body(m, families)
    n_body = len(body)

    cap = etym_capacity(m)
    n_etym = len(flow1(etym_items(etym), cap, etym_height))
    list_start = n_etym + 1
    heb_start = list_start + n_body

    shifted = {k: v + (list_start - 1) for k, v in species_page.items()}
    shifted_fam = {k: v + (list_start - 1) for k, v in fam_page.items()}
    cap_h = (m.page_h - m.margin_top - HEB_TOP_INSET) - m.margin_bot
    hebrew_pages = flow2(hebrew_items(records, shifted), cap_h, heb_height,
                         ncols=args.hebrew_columns)
    eng_pages = flow2(english_items(records, shifted), cap_h, eng_height,
                      ncols=ENG_COLUMNS)

    lat_start = heb_start + len(hebrew_pages) + len(eng_pages)
    lat_pages = flow2(latin_family_items(families, shifted_fam), cap_h,
                      latin_family_height, ncols=3)
    heb_fam_start = lat_start + len(lat_pages)
    heb_fam_pages = flow2(hebrew_family_items(families, shifted_fam), cap_h,
                          hebrew_family_height, ncols=3)

    out = os.path.join(os.path.dirname(args.out), "preview-families.pdf")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c = canvas.Canvas(out, pagesize=(m.page_w, m.page_h),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle("Birds of Israel — family indexes preview")
    c.setAuthor(AUTHOR)
    c.setCreator("book/make_pocket.py --preview-families")

    for i, cols in enumerate(lat_pages):
        draw_latin_family_page(c, m, cols, lat_start + i, letter_stack=True)
        c.showPage()
    for i, cols in enumerate(heb_fam_pages):
        draw_hebrew_family_page(c, m, cols, heb_fam_start + i,
                                letter_stack=True)
        c.showPage()
    c.save()

    print(f"Wrote {out}")
    print(f"  Latin families: {len(lat_pages)} pages, "
          f"folios {lat_start}–{lat_start + len(lat_pages) - 1}")
    print(f"  Hebrew families: {len(heb_fam_pages)} pages, "
          f"folios {heb_fam_start}–{heb_fam_start + len(heb_fam_pages) - 1}")
    print(f"  References point to list pages {list_start}–"
          f"{list_start + n_body - 1}")


def render_latin_species_preview(args):
    """Proof of the Latin species index, two columns."""
    register_fonts()
    m = Metrics(args.base)
    records, families = load(args.data, args.order_source)
    etym = Etymology(args.etym, part_color=K(0.70), dot_color=K(0.70),
                     plain_color=K(1.00))

    body, fam_page, species_page = paginate_body(m, families)
    n_body = len(body)

    cap = etym_capacity(m)
    n_etym = len(flow1(etym_items(etym), cap, etym_height))
    list_start = n_etym + 1
    heb_start = list_start + n_body

    shifted = {k: v + (list_start - 1) for k, v in species_page.items()}
    shifted_fam = {k: v + (list_start - 1) for k, v in fam_page.items()}
    cap_h = (m.page_h - m.margin_top - HEB_TOP_INSET) - m.margin_bot
    hebrew_pages = flow2(hebrew_items(records, shifted), cap_h, heb_height,
                         ncols=args.hebrew_columns)
    eng_pages = flow2(english_items(records, shifted), cap_h, eng_height,
                      ncols=ENG_COLUMNS)
    lat_fam_start = heb_start + len(hebrew_pages) + len(eng_pages)
    lat_pages = flow2(latin_family_items(families, shifted_fam), cap_h,
                      latin_family_height, ncols=3)
    heb_fam_start = lat_fam_start + len(lat_pages)
    heb_fam_pages = flow2(hebrew_family_items(families, shifted_fam), cap_h,
                          hebrew_family_height, ncols=3)
    lat_species_start = heb_fam_start + len(heb_fam_pages)

    lat_species_pages = flow2(latin_species_items(records, shifted), cap_h,
                              latin_species_height, ncols=2)

    out = os.path.join(os.path.dirname(args.out),
                       "preview-latin-species.pdf")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c = canvas.Canvas(out, pagesize=(m.page_w, m.page_h),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle("Birds of Israel — Latin species index preview")
    c.setAuthor(AUTHOR)
    c.setCreator("book/make_pocket.py --preview-latin-species")

    for i, cols in enumerate(lat_species_pages):
        draw_latin_species_page(c, m, cols, lat_species_start + i,
                                letter_stack=True)
        c.showPage()
    c.save()

    last = lat_species_start + len(lat_species_pages) - 1
    print(f"Wrote {out}")
    print(f"  Latin species index, 2 columns: {len(lat_species_pages)} pages, "
          f"folios {lat_species_start}–{last}")
    print(f"  References point to list pages {list_start}–"
          f"{list_start + n_body - 1}")


def render_themes_preview(args, sort_hebrew=True,
                          name="preview-themes.pdf"):
    """Proof of the themed element data pages with variant cross-references."""
    register_fonts()
    m = Metrics(args.base)
    etym = Etymology(args.etym, part_color=K(0.70), dot_color=K(0.70),
                     plain_color=K(1.00))

    cap = etym_capacity(m)
    pages = flow1(etym_items(etym, sort_hebrew=sort_hebrew), cap, etym_height)

    out = os.path.join(os.path.dirname(args.out), name)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c = canvas.Canvas(out, pagesize=(m.page_w, m.page_h),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle("Birds of Israel — themed word elements preview")
    c.setAuthor(AUTHOR)
    c.setCreator("book/make_pocket.py --preview-themes"
                 + ("-hebrew" if sort_hebrew else ""))

    for i, items in enumerate(pages, start=1):
        draw_etym_page(c, m, items, i)
        c.showPage()
    c.save()

    print(f"Wrote {out}")
    print(f"  Themed elements: {len(pages)} pages, folios 1–{len(pages)}")


def render_key_preview(args):
    """Proof of the “How to read this book” page."""
    register_fonts()
    m = Metrics(args.base)
    etym = Etymology(args.etym, part_color=K(0.70), dot_color=K(0.70),
                     plain_color=K(1.00))

    out = os.path.join(os.path.dirname(args.out), "preview-key.pdf")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c = canvas.Canvas(out, pagesize=(m.page_w, m.page_h),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle("Birds of Israel — key page preview")
    c.setAuthor(AUTHOR)
    c.setCreator("book/make_pocket.py --preview-key")

    draw_key_page(c, m, etym)
    draw_roman_folio(c, m, 5)
    c.showPage()
    c.save()

    print(f"Wrote {out}")


def render_elements_preview(args):
    """Proof of the alphabetical word-element index, three columns."""
    register_fonts()
    m = Metrics(args.base)
    records, families = load(args.data, args.order_source)
    etym = Etymology(args.etym, part_color=K(0.70), dot_color=K(0.70),
                     plain_color=K(1.00))

    body, fam_page, species_page = paginate_body(m, families)
    n_body = len(body)

    cap = etym_capacity(m)
    n_etym = len(flow1(etym_items(etym), cap, etym_height))
    list_start = n_etym + 1
    heb_start = list_start + n_body

    shifted = {k: v + (list_start - 1) for k, v in species_page.items()}
    shifted_fam = {k: v + (list_start - 1) for k, v in fam_page.items()}
    cap_h = (m.page_h - m.margin_top - HEB_TOP_INSET) - m.margin_bot
    hebrew_pages = flow2(hebrew_items(records, shifted), cap_h, heb_height,
                         ncols=args.hebrew_columns)
    eng_pages = flow2(english_items(records, shifted), cap_h, eng_height,
                      ncols=ENG_COLUMNS)
    lat_fam_start = heb_start + len(hebrew_pages) + len(eng_pages)
    lat_pages = flow2(latin_family_items(families, shifted_fam), cap_h,
                      latin_family_height, ncols=3)
    heb_fam_start = lat_fam_start + len(lat_pages)
    heb_fam_pages = flow2(hebrew_family_items(families, shifted_fam), cap_h,
                          hebrew_family_height, ncols=3)
    lat_species_start = heb_fam_start + len(heb_fam_pages)
    lat_species_pages = flow2(latin_species_items(records, shifted), cap_h,
                              latin_species_height, ncols=2)
    el_start = lat_species_start + len(lat_species_pages)

    items = element_index_items(etym, records, shifted, cap)
    el_cap = (m.page_h - m.margin_top - EL_TOP_INSET) - m.margin_bot
    el_pages = flow2(items, el_cap, element_index_height, ncols=1)

    out = os.path.join(os.path.dirname(args.out), "preview-elements.pdf")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    c = canvas.Canvas(out, pagesize=(m.page_w, m.page_h),
                      initialFontName="BirdLatin", initialFontSize=10)
    c.setTitle("Birds of Israel — word elements index preview")
    c.setAuthor(AUTHOR)
    c.setCreator("book/make_pocket.py --preview-elements")

    for i, cols in enumerate(el_pages):
        draw_element_index_page(c, m, cols, el_start + i,
                                letter_stack=True, first_page=(i == 0))
        c.showPage()
    c.save()

    last = el_start + len(el_pages) - 1
    print(f"Wrote {out}")
    print(f"  Word elements index, 1 column: {len(el_pages)} pages, "
          f"folios {el_start}–{last}")
    print(f"  Themed pages 1–{n_etym}; list references {list_start}–"
          f"{list_start + n_body - 1}")


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
    ap.add_argument("--preview-hebrew", action="store_true",
                    help="write only the Hebrew index as preview-hebrew.pdf, "
                         "with its final folios and page references")
    ap.add_argument("--preview-english", action="store_true",
                    help="write only the English index as preview-english.pdf")
    ap.add_argument("--preview-families", action="store_true",
                    help="write the Latin and Hebrew family indexes as "
                         "preview-families.pdf")
    ap.add_argument("--preview-latin-species", action="store_true",
                    help="write the Latin species index as "
                         "preview-latin-species.pdf")
    ap.add_argument("--preview-elements", action="store_true",
                    help="write the word-elements index as preview-elements.pdf")
    ap.add_argument("--preview-themes", action="store_true",
                    help="write the themed element data pages as "
                         "preview-themes.pdf")
    ap.add_argument("--preview-themes-hebrew", action="store_true",
                    help="write a Hebrew-sorted themed preview as "
                         "preview-themes-hebrew.pdf")
    ap.add_argument("--preview-key", action="store_true",
                    help="write the “How to read this book” page as "
                         "preview-key.pdf")
    ap.add_argument("--hebrew-columns", type=int, choices=(2, 3),
                    default=HEB_COLUMNS,
                    help="columns in the Hebrew index preview (default 3)")
    args = ap.parse_args()
    if args.preview_hebrew:
        render_hebrew_preview(args)
    elif args.preview_english:
        render_english_preview(args)
    elif args.preview_families:
        render_families_preview(args)
    elif args.preview_latin_species:
        render_latin_species_preview(args)
    elif args.preview_elements:
        render_elements_preview(args)
    elif args.preview_themes:
        render_themes_preview(args)
    elif args.preview_themes_hebrew:
        render_themes_preview(args, sort_hebrew=True,
                              name="preview-themes-hebrew.pdf")
    elif args.preview_key:
        render_key_preview(args)
    else:
        render(args)


if __name__ == "__main__":
    main()
