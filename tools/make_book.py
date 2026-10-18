#!/usr/bin/env python3
"""Generate the 'Birds of Israel' genus learning sheets as a print-ready A4 PDF.

Two modes:

  compact (default)  Pack many genus blocks per page, flowing down column 1 then
                     column 2. A genus block is never split across a column or a
                     page boundary. The first and last genus on each page are
                     printed in the top-left and top-right corners so you can
                     navigate a printed stack.

  wall               One genus per page with large type, for wall display.

Shared layout rules:
  * Species rows occupy equal-height slots; each baseline sits in the vertical
    centre of its slot and each separator is drawn on the slot boundary, i.e.
    exactly halfway between two consecutive baselines.
  * Latin name is left-aligned, Hebrew name right-aligned, one line each.
  * Font sizes shrink automatically when names are long, so nothing overflows.

Usage:
  python3 tools/make_book.py --mode compact --out out/israel_birds_compact.pdf
  python3 tools/make_book.py --mode wall    --limit 2 --out out/review.pdf
"""

import argparse
import json
import os
import tempfile

from bidi.algorithm import get_display
from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------- fonts

LATIN_CANDIDATES = [
    "/usr/share/fonts/google-noto-vf/NotoSansMono[wght].ttf",
    "/usr/share/fonts/liberation-mono-fonts/LiberationMono-Regular.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
]
HEBREW_CANDIDATES = [
    "/usr/share/fonts/google-droid-sans-fonts/DroidSansHebrew-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf",
]

BLACK = black
GREY = HexColor("#6B6B6B")
FAINT = HexColor("#9A9A9A")
LIGHT_RULE = HexColor("#DCDCDC")
MID_RULE = HexColor("#8A8A8A")


def pick(candidates, what):
    for path in candidates:
        if os.path.exists(path):
            return path
    raise SystemExit(f"No {what} font found. Tried:\n  " + "\n  ".join(candidates))


_HEB_CMAP = None
MAQAF = "־"          # Hebrew hyphen; the correct character in these names


def hebrew_glyphs():
    """Codepoints available in the Hebrew font, for a loud failure on tofu."""
    global _HEB_CMAP
    if _HEB_CMAP is None:
        from fontTools.ttLib import TTFont
        cmap = set()
        for table in TTFont(pick(HEBREW_CANDIDATES, "Hebrew"))["cmap"].tables:
            cmap |= set(table.cmap.keys())
        _HEB_CMAP = cmap
    return _HEB_CMAP


def hebrew_text(s):
    """Normalise a Hebrew name for printing.

    Israeli bird names use an ASCII hyphen between compound parts
    (``לבנת-בטן``); in Hebrew that character is the maqaf, which is also the only
    one the font carries. Unsupported codepoints raise rather than print as tofu.
    """
    if not s:
        return s
    s = s.replace("-", MAQAF)
    missing = sorted({c for c in s if c != " " and ord(c) not in hebrew_glyphs()})
    if missing:
        raise SystemExit(
            "Hebrew font lacks these characters: "
            + ", ".join(f"U+{ord(c):04X} {c!r}" for c in missing)
            + f"\nin: {s!r}")
    return s


def bold_latin(latin_path):
    """A bold companion from the same family.

    NotoSansMono ships as a variable font, so instance it at weight 700; using
    a different family for the headings would break the page's texture.
    """
    from fontTools.ttLib import TTFont as FTFont
    f = FTFont(latin_path)
    if "fvar" not in f:
        for cand in (latin_path.replace("-Regular", "-Bold"),
                     latin_path.replace(".ttf", "-Bold.ttf")):
            if os.path.exists(cand):
                return cand
        return None
    from fontTools.varLib.instancer import instantiateVariableFont
    inst = instantiateVariableFont(f, {"wght": 700})
    fd, out = tempfile.mkstemp(suffix=".ttf", prefix="BirdMonoBold-")
    os.close(fd)
    inst.save(out)
    return out


def register_fonts():
    latin, hebrew = pick(LATIN_CANDIDATES, "Latin"), pick(HEBREW_CANDIDATES, "Hebrew")
    for name, path in (("BirdLatin", latin), ("BirdHebrew", hebrew)):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, path))
    if "BirdLatinBold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("BirdLatinBold", bold_latin(latin) or latin))
    return latin, hebrew


def w(text, font, size, rtl=False):
    """Width of a string, applying bidi reordering first when it is Hebrew."""
    return pdfmetrics.stringWidth(get_display(hebrew_text(text)) if rtl else text,
                                  font, size)


# ---------------------------------------------------------------- metrics

class Metrics:
    """All page/layout numbers, derived from a mode and a chosen base font size."""

    def __init__(self, mode, base, header_lines=2):
        self.mode = mode
        self.base = base                      # species font size (Latin), points
        self.heb = base * 1.06
        self.row_h = base * 1.62              # vertical slot per species row
        self.header_lines = header_lines      # lines reserved for the genus list

        if mode == "compact":
            self.margin_x, self.margin_top, self.margin_bot = 11 * mm, 12 * mm, 12 * mm
            self.cols, self.gutter = 2, 7 * mm
            self.genus_size, self.family_size = base * 1.30, base * 0.78
            self.block_gap = 3.4 * mm
            self.rule_gap = 1.1 * mm
            self.header_max = base * 0.86     # running head: every genus on the page
            self.header_floor = 5.0
        else:
            self.margin_x, self.margin_top, self.margin_bot = 38 * mm, 20 * mm, 32 * mm
            self.cols, self.gutter = 1, 0
            self.genus_size, self.family_size = 26.0, 10.5
            self.block_gap = 0
            self.rule_gap = 3.0 * mm
            self.header_max = self.header_floor = 0

        self.page_w, self.page_h = A4
        # the header occupies the top of the page; the body starts below it
        self.header_h = (self.header_lines * self.header_max * 1.5 + 3.5 * mm
                         if self.header_max else 0)
        self.col_top = self.page_h - self.margin_top - self.header_h
        self.col_bottom = self.margin_bot
        self.col_w = ((self.page_w - 2 * self.margin_x)
                      - self.gutter * (self.cols - 1)) / self.cols
        self.col_x = [self.margin_x + i * (self.col_w + self.gutter)
                      for i in range(self.cols)]

    def available(self):
        return self.col_top - self.col_bottom


# ---------------------------------------------------------------- genus blocks

def group_genera(records):
    """Turn flat species records into ordered genus blocks."""
    blocks = {}
    order = []
    for r in records:
        g = r["genus"]
        if g not in blocks:
            blocks[g] = {"genus": g, "family": r["family"],
                         "family_he": r.get("family_he", ""),
                         "order": r["order"], "species": []}
            order.append(g)
        blocks[g]["species"].append(r)
    # genus -> family must be unique, otherwise the grouping is wrong
    for g in order:
        fams = {s["family"] for s in blocks[g]["species"]}
        if len(fams) > 1:
            raise SystemExit(f"genus {g} spans families {sorted(fams)}")
        # alphabetical within the genus
        blocks[g]["species"].sort(key=lambda s: s["latin"])
    return [blocks[g] for g in sorted(order)]


def block_height(m, blk):
    n = len(blk["species"])
    head = m.genus_size * 1.05 + m.family_size * 1.55 + m.rule_gap
    return head + n * m.row_h + m.rule_gap + m.block_gap


def _marker(sp):
    """Status code to print beside a name: A=accidental, I=introduced, etc."""
    return (sp.get("status") or "").strip()


def latin_size_for(m, blk):
    """Largest size <= base at which every row of this block fits its column."""
    avail = m.col_w - 5 * mm
    size = m.base
    for _ in range(40):
        widest = 0.0
        for sp in blk["species"]:
            mk = _marker(sp)
            need = (w(sp["latin"], "BirdLatin", size)
                    + w(sp["hebrew"], "BirdHebrew", size * 1.06, rtl=True))
            if mk:
                need += w(f" {mk}", "BirdLatin", size * 0.72) + 1.5
            widest = max(widest, need)
        if widest <= avail or size <= m.base * 0.72:
            break
        size *= avail / widest * 0.999
    return size


def draw_block(c, m, blk, x_left, top):
    right = x_left + m.col_w
    size = latin_size_for(m, blk)
    heb = size * 1.06

    # genus heading, then family, then a rule
    c.setFillColor(BLACK)
    c.setFont("BirdLatin", m.genus_size)
    c.drawString(x_left, top - m.genus_size * 0.88, blk["genus"])

    fam_latin, fam_he = blk["family"], blk.get("family_he", "")
    fy = top - m.genus_size * 1.05 - m.family_size * 1.05
    c.setFillColor(GREY)
    c.setFont("BirdLatin", m.family_size)
    c.drawString(x_left, fy, fam_latin)
    if fam_he:
        c.setFont("BirdHebrew", m.family_size * 1.06)
        c.drawRightString(right, fy, get_display(hebrew_text(fam_he)))

    rule_y = fy - m.family_size * 0.55 - m.rule_gap * 0.5
    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.7)
    c.line(x_left, rule_y, right, rule_y)

    n = len(blk["species"])
    mk_size = size * 0.72
    for i, sp in enumerate(blk["species"]):
        slot_top = rule_y - i * m.row_h
        baseline = slot_top - m.row_h / 2 - size * 0.34
        mk = _marker(sp)
        mk_w = (w(f" {mk}", "BirdLatin", mk_size) + 1.5) if mk else 0.0

        c.setFillColor(BLACK)
        c.setFont("BirdLatin", size)
        c.drawString(x_left, baseline, sp["latin"])

        hebrew = sp["hebrew"]
        if hebrew:
            c.setFont("BirdHebrew", heb)
            c.setFillColor(BLACK)
            c.drawRightString(right - mk_w, baseline, get_display(hebrew_text(hebrew)))
        else:                                   # unresolved name: leave a visible gap
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


# ---------------------------------------------------------------- running head

def wrap_to_width(text, font, size, first_w, rest_w):
    """Greedy wrap on ', ' boundaries; line 1 is narrower (shares with the number)."""
    lines, cur = [], ""
    for word in text.split(", "):
        piece = word if not cur else cur + ", " + word
        limit = first_w if not lines else rest_w
        if cur and w(piece, font, size) > limit:
            lines.append(cur)
            cur = word
        else:
            cur = piece
    if cur:
        lines.append(cur)
    return lines


def header_layout(m, genera, page_num, cap=None):
    """Fit 'Acrocephalus, Actitis, ...' and the page number into the header band.

    The full genus list runs to ~210 characters, which cannot fit one line at a
    readable size, so it wraps over the reserved lines and shrinks only if it
    still does not fit.
    """
    text = ", ".join(genera)
    full = m.page_w - 2 * m.margin_x
    size = cap or m.header_max
    first = full - w(page_num, "BirdLatin", size) - 4 * mm

    while size > m.header_floor:
        lines = wrap_to_width(text, "BirdLatin", size, first, full)
        if len(lines) <= m.header_lines:
            return size, lines
        size -= 0.25
        first = full - w(page_num, "BirdLatin", size) - 4 * mm
    return m.header_floor, wrap_to_width(text, "BirdLatin", m.header_floor, first, full)


def document_header_size(m, pages, total):
    """One header size for the whole document, so every page looks identical."""
    size = m.header_max
    for i, page in enumerate(pages, start=1):
        genera = [blk["genus"] for col in page for blk, _ in col]
        size = min(size, header_layout(m, genera, f"{i}/{total}", cap=size)[0])
    return size


def draw_header(c, m, genera, page_num, size):
    size, lines = header_layout(m, genera, page_num, cap=size)
    top = m.page_h - m.margin_top
    c.setFillColor(GREY)
    c.setFont("BirdLatin", size)
    y = top - size
    for line in lines:
        c.drawString(m.margin_x, y, line)
        y -= size * 1.5
    c.setFillColor(BLACK)
    c.setFont("BirdLatin", size)
    c.drawRightString(m.page_w - m.margin_x, top - size, page_num)


# ---------------------------------------------------------------- page flow

def paginate(m, blocks):
    """Flow blocks down column 1 then column 2, never splitting a block.

    A block moves to the next column when it does not fit in what is left of the
    current one. It is force-placed only into a genuinely *empty* column, which
    can only happen if a single block is taller than a whole column.
    """
    if m.mode == "wall":                      # one genus per page, by definition
        return [[[(blk, m.col_top)]] for blk in blocks]

    pages = []
    page = [[] for _ in range(m.cols)]
    empty = [True] * m.cols
    col, y = 0, m.col_top

    for blk in blocks:
        h = block_height(m, blk)
        while True:
            if (y - h) >= m.col_bottom or empty[col]:
                break
            col += 1
            if col >= m.cols:                      # both columns full -> new page
                pages.append(page)
                page = [[] for _ in range(m.cols)]
                empty = [True] * m.cols
                col = 0
            y = m.col_top
        page[col].append((blk, y))      # the block's top edge is the current y
        y -= h                          # ...and it consumes h of the column
        empty[col] = False

    pages.append(page)
    _check_no_overlap(m, pages)
    return pages


def _check_no_overlap(m, pages):
    """Guard against the packing bug where two blocks occupy the same space."""
    for pno, page in enumerate(pages, start=1):
        for ci, col in enumerate(page):
            bottom = m.col_top
            for blk, top in col:
                h = block_height(m, blk)
                if top > bottom + 0.01:
                    raise AssertionError(
                        f"page {pno} col {ci}: '{blk['genus']}' top {top:.1f} "
                        f"overlaps previous block bottom {bottom:.1f}")
                if top - h < m.col_bottom - 0.01 and len(col) > 1:
                    raise AssertionError(
                        f"page {pno} col {ci}: '{blk['genus']}' runs past the "
                        f"column bottom ({top - h:.1f} < {m.col_bottom:.1f})")
                bottom = top - h


# ---------------------------------------------------------------- legend

LEGEND = [
    ("A",  "Accidental — a species that rarely or accidentally occurs in Israel"),
    ("I",  "Introduced — a species introduced to Israel as a consequence, "
           "direct or indirect, of human actions"),
    ("Ex", "Extirpated — a species that no longer occurs in Israel although "
           "populations exist elsewhere"),
    ("X",  "Extinct — a species or subspecies that no longer exists"),
    ("—", "No marker: a commonly occurring native species"),
]


def wrap_words(text, font, size, width):
    """Wrap a sentence on spaces to fit `width`."""
    lines, cur = [], ""
    for word in text.split():
        piece = word if not cur else cur + " " + word
        if cur and w(piece, font, size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = piece
    if cur:
        lines.append(cur)
    return lines


def draw_legend_page(c, m, pno, total):
    """Final page: what the A / I / Ex / X markers beside a Hebrew name mean."""
    top = m.page_h - m.margin_top
    c.setFillColor(BLACK)
    c.setFont("BirdLatin", m.header_max)
    c.drawRightString(m.page_w - m.margin_x, top - m.header_max, f"{pno} / {total}")

    full = m.page_w - 2 * m.margin_x
    y = top - m.header_h - m.genus_size * 1.4
    c.setFont("BirdLatin", m.genus_size)
    c.drawString(m.margin_x, y, "Key")

    y -= m.base * 1.5
    c.setFillColor(GREY)
    c.setFont("BirdLatin", m.family_size)
    c.drawString(m.margin_x, y, "Markers printed to the right of a Hebrew name")

    y -= m.base * 1.2
    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.8)
    c.line(m.margin_x, y, m.page_w - m.margin_x, y)

    marker_w = w("Ex", "BirdLatin", m.base) + 14 * mm      # widest marker + gutter
    body_w = full - marker_w
    line_h = m.base * 1.35
    wrapped = [(mk, wrap_words(txt, "BirdLatin", m.base, body_w)) for mk, txt in LEGEND]
    # equal-height rows, so one-line and two-line entries share the same rhythm
    row_h = max(len(ls) for _, ls in wrapped) * line_h + m.base

    for idx, (marker, lines) in enumerate(wrapped):
        block_h = len(lines) * line_h
        baseline = y - (row_h - block_h) / 2 - m.base * 0.75
        c.setFillColor(BLACK)
        c.setFont("BirdLatin", m.base)
        c.drawString(m.margin_x, baseline, marker)
        c.setFillColor(HexColor("#333333"))
        for i, line in enumerate(lines):
            c.drawString(m.margin_x + marker_w, baseline - i * line_h, line)
        y -= row_h
        if idx < len(wrapped) - 1:
            c.setStrokeColor(LIGHT_RULE)
            c.setLineWidth(0.5)
            c.line(m.margin_x, y, m.page_w - m.margin_x, y)

    y -= m.base * 1.2
    c.setStrokeColor(MID_RULE)
    c.setLineWidth(0.8)
    c.line(m.margin_x, y, m.page_w - m.margin_x, y)

    y -= m.base * 1.8
    c.setFillColor(GREY)
    c.setFont("BirdLatin", m.family_size)
    note = ("The markers only flag exceptions, so an unmarked species is simply one "
            "that falls into none of these categories — not a statement about how "
            "likely you are to meet it. Season and abundance are not encoded here.")
    for line in wrap_words(note, "BirdLatin", m.family_size, full):
        c.drawString(m.margin_x, y, line)
        y -= m.family_size * 1.4
    c.showPage()


def render(m, pages, out, title, legend=True):
    c = canvas.Canvas(out, pagesize=A4)
    c.setTitle(title)
    total = len(pages) + (1 if legend and m.mode == "compact" else 0)
    hsize = document_header_size(m, pages, total) if m.mode == "compact" else 0
    for pno, page in enumerate(pages, start=1):
        # every genus on the page, in reading order (column 1 then column 2)
        genera = [blk["genus"] for col in page for blk, _ in col]

        if m.mode == "compact":
            draw_header(c, m, genera, f"{pno} / {total}", hsize)
        else:
            c.setFillColor(FAINT)
            c.setFont("BirdLatin", 8)
            c.drawCentredString(m.page_w / 2, m.page_h - 7.5 * mm, f"{pno}/{total}")

        for ci, col in enumerate(page):
            for blk, top in col:
                draw_block(c, m, blk, m.col_x[ci], top)
        c.showPage()
    if legend and m.mode == "compact":
        draw_legend_page(c, m, len(pages) + 1, total)
    c.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/israel_birds_final.json")
    ap.add_argument("--out", default="out/israel_birds.pdf")
    ap.add_argument("--mode", choices=["compact", "wall"], default="compact")
    ap.add_argument("--base", type=float, default=0, help="species font size (pt)")
    ap.add_argument("--limit", type=int, default=0, help="only first N genera")
    ap.add_argument("--genera", default="",
                    help="comma-separated genus names to include, e.g. Columba,Streptopelia")
    ap.add_argument("--regular-only", action="store_true",
                    help="drop accidental/vagrant species")
    ap.add_argument("--no-legend", action="store_true",
                    help="omit the final key/legend page")
    args = ap.parse_args()

    latin_path, hebrew_path = register_fonts()
    records = json.load(open(args.data, encoding="utf-8"))
    if args.regular_only:
        records = [r for r in records if not r.get("status")]
    blocks = group_genera(records)
    if args.genera:
        want = [g.strip() for g in args.genera.split(",") if g.strip()]
        have = {b["genus"] for b in blocks}
        unknown = [g for g in want if g not in have]
        if unknown:
            raise SystemExit(f"genera not in the data: {unknown}")
        blocks = [b for b in blocks if b["genus"] in want]
    if args.limit:
        blocks = blocks[:args.limit]

    base = args.base or (10.0 if args.mode == "compact" else 15.0)

    # The header reservation feeds back into pagination (a taller header means a
    # shorter column means different contents), so settle it iteratively.
    m, pages, header_lines = None, None, 2
    for _ in range(5):
        m = Metrics(args.mode, base, header_lines)
        pages = paginate(m, blocks)
        if m.mode != "compact":
            break
        needed = max(
            (len(header_layout(m, [b["genus"] for col in p for b, _ in col],
                               f"{i}/{len(pages)}")[1])
             for i, p in enumerate(pages, start=1)), default=1)
        if needed <= header_lines:
            break
        header_lines = needed

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    render(m, pages, args.out, "Birds of Israel — genus learning sheets")

    species = sum(len(b["species"]) for b in blocks)
    print(f"Wrote {args.out}")
    print(f"  mode={args.mode} base={base}pt cols={m.cols}")
    print(f"  {len(blocks)} genera, {species} species -> {len(pages)} pages")
    print(f"  Latin font : {latin_path}")
    print(f"  Hebrew font: {hebrew_path}")


if __name__ == "__main__":
    main()
