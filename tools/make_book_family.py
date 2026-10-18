#!/usr/bin/env python3
"""Birds of Israel -- FAMILY-grouped variant (alternative to make_book.py).

Same page furniture as make_book.py (two columns, one line per species, Latin
left / Hebrew right, automatic shrinking, key page), but a different organising
principle:

  * Species are grouped FAMILY first, then alphabetically by genus, then by
    species. Families are alphabetical, genera alphabetical within a family.
  * The body shows a FAMILY heading spanning the column, with its genus blocks
    underneath. The family is stated once instead of on every genus.
  * The running head lists one FAMILY PER ROW, with the genera of that family
    that appear on the page. The page number sits at the top right.

Rules preserved from the other variant: a genus block is never split across a
column or page, and a family heading is never orphaned -- it always travels with
at least its first genus block. A family that is too tall for one column may
continue in the next, and its heading is repeated there.

Usage:
  python3 tools/make_book_family.py --out out/israel_birds_by_family.pdf
  python3 tools/make_book_family.py --regular-only --base 10.5 --out ...
"""

import argparse
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import make_book as base                                  # shared helpers
from make_book import (BLACK, FAINT, GREY, LIGHT_RULE, MID_RULE,
                       draw_legend_page, get_display, hebrew_text, wrap_words, w)
from etym import ENTRY_H, THEME_H, Etymology, glossary_pages
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

STRONG_RULE = HexColor("#3A3A3A")
BODY_INK = HexColor("#222222")
QUIET_INK = HexColor("#333333")


# ---------------------------------------------------------------- geometry

class Metrics:
    """Same names as make_book.Metrics so the shared legend page works."""

    def __init__(self, base_size, header_size, header_h):
        self.mode = "family"
        self.base = base_size
        self.row_h = base_size * 1.62
        self.margin_x, self.margin_top, self.margin_bot = 11 * mm, 12 * mm, 12 * mm
        self.cols, self.gutter = 2, 7 * mm
        self.genus_size = base_size * 1.24
        self.family_head_size = base_size * 1.46
        self.family_size = base_size * 0.78       # for the key page subtitle
        self.block_gap = 3.2 * mm
        self.rule_gap = 1.1 * mm

        self.page_w, self.page_h = A4
        self.header_max = header_size
        self.header_h = header_h
        self.col_top = self.page_h - self.margin_top - header_h
        self.col_bottom = self.margin_bot
        self.col_w = ((self.page_w - 2 * self.margin_x)
                      - self.gutter * (self.cols - 1)) / self.cols
        self.col_x = [self.margin_x + i * (self.col_w + self.gutter)
                      for i in range(self.cols)]


def family_head_height(m):
    """Height of a family heading inside the body (name + rule + breathing room)."""
    return m.family_head_size * 1.4 + 2.4 * mm


def block_height(m, blk):
    """A genus block: genus name + rule + one line per species + closing rule."""
    head = m.genus_size * 1.05 + m.rule_gap
    return head + len(blk["species"]) * m.row_h + m.rule_gap + m.block_gap


# ---------------------------------------------------------------- grouping

def group_by_family(records):
    """family (alphabetical) -> genus (alphabetical) -> species (alphabetical)."""
    fams = {}
    for r in records:
        f = fams.setdefault(r["family"], {"family": r["family"],
                                          "family_he": r.get("family_he", ""),
                                          "genera": {}})
        g = f["genera"].setdefault(r["genus"], {"genus": r["genus"],
                                                "family": r["family"],
                                                "species": []})
        g["species"].append(r)
    out = []
    for name in sorted(fams):
        f = fams[name]
        blocks = []
        for gname in sorted(f["genera"]):
            blk = f["genera"][gname]
            blk["species"].sort(key=lambda s: s["latin"])
            blocks.append(blk)
        out.append({"family": name, "family_he": f["family_he"], "blocks": blocks})
    return out


# ---------------------------------------------------------------- pagination

def paginate(m, families, page_height):
    """Flow families down column 1 then column 2, keeping each family on one page.

    `page_height(pno)` is the running-head reservation for a page, so a page only
    gives up the room its own head needs.

    A family is placed as a unit: it may fill the rest of the current column and
    continue into the next column *of the same page*, but it will never start
    unless it can finish on that page. When it cannot, the page is cut short --
    the remaining space is left blank -- and the whole family starts on the next
    page. The only exception is a family taller than a whole page, which has to
    span and is the sole case where a family crosses a page boundary.
    """
    pages = []
    page = [[] for _ in range(m.cols)]
    empty = [True] * m.cols
    col_family = [None] * m.cols          # family heading already printed here
    pno, col = 0, 0

    def top():
        return m.page_h - m.margin_top - page_height(pno)

    col_y = [top()] * m.cols

    def start_page():
        nonlocal page, empty, col_family, col_y, col, pno
        pages.append(page)
        pno += 1
        page = [[] for _ in range(m.cols)]
        empty = [True] * m.cols
        col_family = [None] * m.cols
        col_y = [top()] * m.cols
        col = 0

    for fam in families:
        blocks = fam["blocks"]
        hh = family_head_height(m)
        total = hh + sum(block_height(m, b) for b in blocks)

        # Decide where this family starts: here, in the next column, or afresh.
        while True:
            free = col_y[col] - m.col_bottom
            if total <= free:
                break                                  # fits in what is left here
            if col < m.cols - 1:
                room = free + (top() - m.col_bottom)   # rest of this page
                if total + hh <= room:                 # +hh for a repeated heading
                    break
            start_page()
            break

        for blk in blocks:
            need_head = col_family[col] != fam["family"]
            h = block_height(m, blk) + (hh if need_head else 0)
            if col_y[col] - h < m.col_bottom and not empty[col]:
                if col < m.cols - 1:
                    col += 1
                    col_y[col] = top()
                else:                                  # family spans a whole page
                    start_page()
                need_head = col_family[col] != fam["family"]
                h = block_height(m, blk) + (hh if need_head else 0)
            if need_head:
                page[col].append(("family", (fam["family"], fam["family_he"])))
                col_y[col] -= hh
                col_family[col] = fam["family"]
            page[col].append(("genus", blk))
            col_y[col] -= block_height(m, blk)
            empty[col] = False

    pages.append(page)
    return pages


def check(m, pages, page_height):
    """No overlaps, no orphaned headings, nothing past the column bottom, and no
    family crossing a page boundary unless it genuinely needs more than a page.

    Returns the families that span pages, so main() can report them.
    """
    where = {}
    for pno, page in enumerate(pages):
        top_limit = m.page_h - m.margin_top - page_height(pno)
        for ci, col in enumerate(page):
            bottom = top_limit
            for i, (kind, val) in enumerate(col):
                if kind == "family":
                    if i + 1 >= len(col):
                        raise AssertionError(
                            f"page {pno + 1} col {ci}: family '{val[0]}' heading orphaned")
                    h = family_head_height(m)
                    where.setdefault(val[0], set()).add(pno)
                else:
                    h = block_height(m, val)
                    where.setdefault(val["family"], set()).add(pno)
                top = bottom - h
                if top < m.col_bottom - 0.01 and len(col) > 1 and bottom < top_limit - 0.01:
                    name = val[0] if kind == "family" else val["genus"]
                    raise AssertionError(
                        f"page {pno + 1} col {ci}: '{name}' runs past the column bottom "
                        f"({top:.1f} < {m.col_bottom:.1f})")
                bottom = top
    return {fam: sorted(p) for fam, p in where.items() if len(p) > 1}


# ---------------------------------------------------------------- drawing

def draw_family_heading(c, m, fam, fam_he, x_left, top):
    right = x_left + m.col_w
    size = m.family_head_size
    c.setFillColor(BLACK)
    c.setFont("BirdLatin", size)
    c.drawString(x_left, top - size * 0.92, fam)
    if fam_he:
        c.setFillColor(GREY)
        c.setFont("BirdHebrew", size * 0.95)
        c.drawRightString(right, top - size * 0.92, get_display(hebrew_text(fam_he)))
    rule_y = top - size * 1.4
    c.setStrokeColor(STRONG_RULE)
    c.setLineWidth(1.1)
    c.line(x_left, rule_y, right, rule_y)
    return rule_y


def draw_genus_block(c, m, blk, x_left, top, etym=None):
    right = x_left + m.col_w
    size = genus_font_size(m, blk, etym)
    heb = size * 1.06

    c.setFillColor(BLACK)
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
    mk_size = size * 0.72
    for i, sp in enumerate(blk["species"]):
        slot_top = rule_y - i * m.row_h
        baseline = slot_top - m.row_h / 2 - size * 0.34
        mk = (sp.get("status") or "").strip()
        mk_w = (w(f" {mk}", "BirdLatin", mk_size) + 1.5) if mk else 0.0

        c.setFillColor(BLACK)
        c.setFont("BirdLatin", size)
        if etym is not None:
            etym.draw_latin(c, x_left, baseline, size, sp["latin"])
        else:
            c.drawString(x_left, baseline, sp["latin"])
        if sp["hebrew"]:
            c.setFont("BirdHebrew", heb)
            c.setFillColor(BLACK)
            c.drawRightString(right - mk_w, baseline, get_display(hebrew_text(sp["hebrew"])))
        else:
            c.setFont("BirdLatin", size)
            c.setFillColor(FAINT)
            c.drawRightString(right - mk_w, baseline, "—")
        if mk:
            c.setFillColor(FAINT)
            c.setFont("BirdLatin", mk_size)
            c.drawRightString(right, baseline, mk)
        if i < n - 1:
            c.setStrokeColor(LIGHT_RULE)
            c.setLineWidth(0.4)
            c.line(x_left, slot_top - m.row_h, right, slot_top - m.row_h)

    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.7)
    c.line(x_left, rule_y - n * m.row_h, right, rule_y - n * m.row_h)


def genus_font_size(m, blk, etym=None):
    """Shrink a genus block's species type until every row fits its column."""
    avail = m.col_w - 5 * mm
    size = m.base
    for _ in range(40):
        widest = 0.0
        for sp in blk["species"]:
            mk = (sp.get("status") or "").strip()
            latin_w = (etym.latin_width(sp["latin"], size) if etym is not None
                       else w(sp["latin"], "BirdLatin", size))
            need = (latin_w
                    + w(sp["hebrew"], "BirdHebrew", size * 1.06, rtl=True))
            if mk:
                need += w(f" {mk}", "BirdLatin", size * 0.72) + 1.5
            widest = max(widest, need)
        if widest <= avail or size <= m.base * 0.72:
            break
        size *= avail / widest * 0.999
    return size


# ---------------------------------------------------------------- running head

def header_rows(page):
    """[(family, [genera on this page])] in reading order.

    A family continuing into the next column gets ONE merged row, not two.
    """
    order, acc = [], {}
    for col in page:
        for kind, val in col:
            fam = val[0] if kind == "family" else val["family"]
            if fam not in acc:
                acc[fam] = []
                order.append(fam)
            if kind == "genus":
                acc[fam].append(val["genus"])
    return [(fam, acc[fam]) for fam in order]


def family_column_width(m, families):
    """Fixed x for the genera column, so family names line up down the page."""
    widest = max((w(f["family"], "BirdLatin", m.header_max) for f in families),
                 default=0)
    return widest + 6 * mm


def header_layout(m, page, page_num, fam_col_w):
    """Rows of 'Family   Genus, Genus, ...' -> (rows_with_lines, n_lines)."""
    full = m.page_w - 2 * m.margin_x
    body_w = full - fam_col_w
    out, n_lines, first = [], 0, True
    for fam, genera in header_rows(page):
        avail = body_w - (w(page_num, "BirdLatin", m.header_max) + 4 * mm if first else 0)
        lines = wrap_words(", ".join(genera), "BirdLatin", m.header_max, avail) or [""]
        out.append((fam, lines))
        n_lines += len(lines)
        first = False
    return out, n_lines


def header_height(m, page, page_num, fam_col_w):
    _, n = header_layout(m, page, page_num, fam_col_w)
    return n * m.header_max * 1.45 + 3.0 * mm


def draw_header(c, m, page, page_num, fam_col_w):
    rows, _ = header_layout(m, page, page_num, fam_col_w)
    top = m.page_h - m.margin_top
    lead = m.header_max * 1.45
    y = top - m.header_max
    c.setFillColor(BLACK)
    c.setFont("BirdLatin", m.header_max)
    c.drawRightString(m.page_w - m.margin_x, y, page_num)
    for i, (fam, lines) in enumerate(rows):
        c.setFillColor(HexColor("#222222"))
        c.setFont("BirdLatin", m.header_max)
        c.drawString(m.margin_x, y, fam)
        c.setFillColor(GREY)
        for j, line in enumerate(lines):
            c.drawString(m.margin_x + fam_col_w, y - j * lead, line)
        y -= lead * len(lines)
    del i


# ---------------------------------------------------------------- glossary

def fit_examples(examples, width, size):
    """Join as many example names as fit, else truncate the first one."""
    out = ""
    for ex in examples[:5]:
        piece = ex if not out else out + ", " + ex
        if out and w(piece, "BirdLatin", size) > width:
            break
        out = piece
    if not out and examples:
        out = examples[0]
        while out and w(out + "...", "BirdLatin", size) > width:
            out = out[:-1]
        out += "..."
    return out


def draw_glossary_page(c, m, rows, pno, total):
    """One page of the themed index, flowed down two columns."""
    top = m.page_h - m.margin_top

    c.setFillColor(BLACK)
    c.setFont("BirdLatin", m.genus_size)
    c.drawString(m.margin_x, top - m.genus_size, "Index of word elements")
    c.setFillColor(GREY)
    c.setFont("BirdLatin", m.header_max)
    c.drawRightString(m.page_w - m.margin_x, top - m.genus_size, f"{pno} / {total}")

    y = top - m.genus_size - m.base * 1.15
    c.setFillColor(QUIET_INK)
    c.setFont("BirdLatin", m.base * 0.76)
    c.drawString(m.margin_x, y,
                 "Grey in the book marks a part listed here; a hyphen shows where it attaches.")
    items_top = y - m.base * 1.10

    for ci, items in enumerate(rows):
        x = m.col_x[ci]
        dash_w = w("-", "BirdLatin", m.base * 0.84)
        x_text = x + dash_w          # letters align; leading dashes sit in the gutter
        x_en = x + 72
        x_he = x + m.col_w

        c.setFillColor(FAINT)
        c.setFont("BirdLatin", m.base * 0.64)
        c.drawString(x_text, items_top, "ELEMENT")
        c.drawString(x_en, items_top, "ENGLISH")
        c.drawRightString(x_he, items_top, "HEBREW")
        c.setStrokeColor(MID_RULE)
        c.setLineWidth(0.6)
        c.line(x, items_top - 5.5, x_he, items_top - 5.5)

        cy = items_top - 18.0
        for i, (kind, val) in enumerate(items):
            if kind == "theme":
                cy -= 3.0
                c.setFillColor(BLACK)
                c.setFont("BirdLatinBold", m.base * 0.80)
                c.drawString(x, cy - m.base * 0.80, val.upper())
                c.setStrokeColor(MID_RULE)
                c.setLineWidth(0.6)
                c.line(x, cy - m.base * 1.35, x_he, cy - m.base * 1.35)
                cy -= THEME_H - 3.0
                continue

            elem, en, he, _examples = val
            baseline = cy - 7.8
            c.setFillColor(BLACK)
            c.setFont("BirdLatin", m.base * 0.84)
            if elem.startswith("-"):
                c.drawString(x, baseline, "-")
                c.drawString(x_text, baseline, elem[1:])
            else:
                c.drawString(x_text, baseline, elem)

            c.setFillColor(BODY_INK)
            c.setFont("BirdLatin", m.base * 0.78)
            c.drawString(x_en, baseline, en)

            c.setFillColor(BODY_INK)
            c.setFont("BirdHebrew", m.base * 0.84)
            c.drawRightString(x_he, baseline, get_display(hebrew_text(he)))

            cy -= ENTRY_H
            if i < len(items) - 1 and items[i + 1][0] != "theme":
                c.setStrokeColor(LIGHT_RULE)
                c.setLineWidth(0.3)
                c.line(x, cy, x_he, cy)
    c.showPage()


# ---------------------------------------------------------------- render

def render(m, pages, out, title, legend=True, families=None, page_height=None,
           etym=None, gloss=None):
    gloss = gloss or []
    c = canvas.Canvas(out, pagesize=A4)
    c.setTitle(title)
    total = len(pages) + (1 if legend else 0) + len(gloss)
    fam_col_w = family_column_width(m, families)

    for pno, page in enumerate(pages, start=1):
        draw_header(c, m, page, f"{pno} / {total}", fam_col_w)
        for ci, col in enumerate(page):
            y = m.page_h - m.margin_top - page_height(pno - 1)
            for kind, val in col:
                if kind == "family":
                    draw_family_heading(c, m, val[0], val[1], m.col_x[ci], y)
                    y -= family_head_height(m)
                else:
                    draw_genus_block(c, m, val, m.col_x[ci], y, etym)
                    y -= block_height(m, val)
        c.showPage()

    if legend:
        # The key is not a content page: give it an ordinary header band rather
        # than this document's largest running-head reservation.
        key_m = copy.copy(m)
        key_m.header_h = 2.0 * m.header_max * 1.45 + 3.0 * mm
        draw_legend_page(c, key_m, len(pages) + 1, total)

    first = len(pages) + (1 if legend else 0) + 1
    for i, rows in enumerate(gloss, start=1):
        draw_glossary_page(c, m, rows, first + i - 1, total)
    c.save()


def m_of(args, header_size, heights, provisional):
    """Metrics for this run; header_h is only the fallback when heights is None."""
    return Metrics(args.base, header_size,
                   max(heights) if heights else provisional)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/israel_birds_final.json")
    ap.add_argument("--out", default="out/israel_birds_by_family.pdf")
    ap.add_argument("--base", type=float, default=10.0, help="species font size (pt)")
    ap.add_argument("--header", type=float, default=0, help="running-head size (pt)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--genera", default="")
    ap.add_argument("--regular-only", action="store_true")
    ap.add_argument("--no-legend", action="store_true")
    ap.add_argument("--etymology", action="store_true",
                    help="split Latin names at morpheme boundaries and add the glossary")
    ap.add_argument("--etym-data", default="data/etymology.json")
    args = ap.parse_args()

    latin_path, hebrew_path = base.register_fonts()
    etym = Etymology(args.etym_data) if args.etymology else None
    gloss = glossary_pages(etym) if etym else []
    records = json.load(open(args.data, encoding="utf-8"))
    if args.regular_only:
        records = [r for r in records if not r.get("status")]
    families = group_by_family(records)
    if args.genera:
        want = {g.strip() for g in args.genera.split(",") if g.strip()}
        for f in families:
            f["blocks"] = [b for b in f["blocks"] if b["genus"] in want]
        families = [f for f in families if f["blocks"]]
    if args.limit:
        families = families[:args.limit]

    header_size = args.header or args.base * 0.82
    provisional = 3.0 * header_size * 1.45 + 3.0 * mm

    # Each page reserves only the head it needs, but that reservation changes
    # what fits on the page, which changes the head. Iterate to a fixed point,
    # then verify every page's head still fits in the room it was given.
    def measure(pages, total):
        m = Metrics(args.base, header_size, provisional)
        fcw = family_column_width(m, families)
        return [header_height(m, p, f"{i} / {total}", fcw)
                for i, p in enumerate(pages, start=1)]

    # Reserve per page, growing the reservation monotonically: a page can then
    # never be given less room than its own head needs, so the fixed point (if
    # reached) is safe and an unconverged run still cannot overflow.
    heights = []
    for _ in range(12):
        pages = paginate(m_of(args, header_size, heights, provisional), families,
                         page_height=lambda pno: (heights[pno] if pno < len(heights)
                                                  else provisional))
        total = len(pages) + (0 if args.no_legend else 1) + len(gloss)
        needed = measure(pages, total)
        grown = [max(needed[i], heights[i]) if i < len(heights) else needed[i]
                 for i in range(len(needed))]
        if grown == heights:
            break
        heights = grown

    if any(n > h + 0.5 for n, h in zip(needed, heights)):
        heights = [max(needed)] * len(needed)          # last resort: one size for all
        pages = paginate(m_of(args, header_size, heights, provisional), families,
                         page_height=lambda pno: heights[pno])
        needed = measure(pages, len(pages) + (0 if args.no_legend else 1) + len(gloss))

    m = m_of(args, header_size, heights, provisional)
    spanning = check(m, pages, lambda pno: heights[pno])
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    render(m, pages, args.out, "Birds of Israel — family learning sheets",
           legend=not args.no_legend, families=families,
           page_height=lambda pno: heights[pno], etym=etym, gloss=gloss)

    species = sum(len(b["species"]) for f in families for b in f["blocks"])
    genera = sum(len(f["blocks"]) for f in families)
    print(f"Wrote {args.out}")
    print(f"  grouping=family  base={args.base}pt head={header_size:.2f}pt "
          f"cols={m.cols}")
    print(f"  per-page head reservation: min={min(heights):.1f}pt max={max(heights):.1f}pt")
    if spanning:
        print(f"  NOTE: {len(spanning)} family/families span pages "
              f"(too tall for one page): {spanning}")
    else:
        print("  every family fits on a single page")
    print(f"  {len(families)} families, {genera} genera, {species} species "
          f"-> {len(pages)} pages (+{'key' if not args.no_legend else 'no key'}"
          f"{f', {len(gloss)} index' if gloss else ''})")
    print(f"  Latin font : {latin_path}")
    print(f"  Hebrew font: {hebrew_path}")


if __name__ == "__main__":
    main()
