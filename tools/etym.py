#!/usr/bin/env python3
"""Etymology-aware rendering helpers.

A word that appears in data/etymology.json is printed as its parts, separated
by a raised dot and set in grey: grey means "this part has an entry in the
index at the back".  A word with no entry is printed whole and black, so the
reader can tell at a glance whether there is anything to look up.

Nothing here draws a page; make_book_family.py calls into it.
"""

import json

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics

PART_GREY = HexColor("#5A5A5A")
DOT_GREY = HexColor("#6B6B6B")

# Heights used by both the pagination and the drawing code, in points.
THEME_H = 21.0
ENTRY_H = 11.2


class Etymology:
    def __init__(self, path="data/etymology.json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.elements = data["elements"]
        self.splits = data["splits"]
        self.themes = data.get("themes", [])

    # ---------------------------------------------------------------- widths

    def __contains__(self, word):
        return word in self.splits

    def _dot_adv(self, size, font):
        return pdfmetrics.stringWidth("M", font, size) * 0.72

    def word_width(self, word, size, font="BirdLatin"):
        parts = self.splits.get(word)
        if not parts:
            return pdfmetrics.stringWidth(word, font, size)
        return (sum(pdfmetrics.stringWidth(s, font, size) for s, _ in parts)
                + (len(parts) - 1) * self._dot_adv(size, font))

    def latin_width(self, latin, size, font="BirdLatin"):
        words = latin.split(" ")
        total = sum(self.word_width(wd, size, font) for wd in words)
        return total + pdfmetrics.stringWidth(" ", font, size) * (len(words) - 1)

    # ---------------------------------------------------------------- drawing

    def _dot(self, c, x, y, size):
        c.setFillColor(DOT_GREY)
        c.circle(x + self._dot_adv(size, "BirdLatin") / 2,
                 y + size * 0.285, size * 0.078, stroke=0, fill=1)

    def draw_word(self, c, x, y, size, word):
        parts = self.splits.get(word)
        if not parts:
            c.setFillColor(HexColor("#000000"))
            c.setFont("BirdLatin", size)
            c.drawString(x, y, word)
            return x + pdfmetrics.stringWidth(word, "BirdLatin", size)

        c.setFont("BirdLatin", size)
        for i, (surface, _) in enumerate(parts):
            if i:
                self._dot(c, x, y, size)
                x += self._dot_adv(size, "BirdLatin")
            c.setFillColor(PART_GREY)
            c.drawString(x, y, surface)
            x += pdfmetrics.stringWidth(surface, "BirdLatin", size)
        return x

    def draw_latin(self, c, x, y, size, latin):
        gap = pdfmetrics.stringWidth(" ", "BirdLatin", size)
        for i, word in enumerate(latin.split(" ")):
            if i:
                x += gap
            x = self.draw_word(c, x, y, size, word)

    # ---------------------------------------------------------------- glossary

    def form_rows(self):
        """One index row per printed surface form.

        Every form gets its own alphabetically placed entry, so a reader who
        sees `phalus` can look up `phalus` rather than having to guess that the
        entry is filed under `cephalus`.  The hyphen shows where that particular
        form attaches.
        """
        usage = {}
        elem_pos = {}
        for word, parts in self.splits.items():
            for i, (surface, eid) in enumerate(parts):
                key = (eid, surface.lower())
                u = usage.setdefault(key, [0, 0])
                if i == 0:
                    u[0] += 1
                if i == len(parts) - 1:
                    u[1] += 1
                ep = elem_pos.setdefault(eid, [0, 0])
                if i == 0:
                    ep[0] += 1
                if i == len(parts) - 1:
                    ep[1] += 1

        rows, seen = [], set()
        for eid, e in self.elements.items():
            for form in e.get("forms", [e["display"]]):
                form = form.lower()
                if (form, e["en"]) in seen:
                    continue
                seen.add((form, e["en"]))
                first, last = usage.get((eid, form), (0, 0))
                if not first and not last:          # form not used in a split
                    first, last = elem_pos.get(eid, (0, 0))
                shown = form
                if first and not last:
                    shown += "-"
                elif last and not first:
                    shown = "-" + shown
                rows.append({"theme": e["theme"], "shown": shown,
                             "key": form, "en": e["en"], "he": e["he"]})
        return rows

    def entry(self, eid):
        """Display form and examples for the index.

        The display comes from the source table (the first listed form); a
        hyphen is added on the side where the element actually attaches.
        """
        e = self.elements[eid]
        first, last = 0, 0
        for word, parts in self.splits.items():
            for i, (surface, eid2) in enumerate(parts):
                if eid2 != eid:
                    continue
                if i == 0:
                    first += 1
                if i == len(parts) - 1:
                    last += 1
        shown = e.get("display") or eid
        if first and not last:
            shown += "-"
        elif last and not first:
            shown = "-" + shown
        examples = sorted({w for w, p in self.splits.items() if any(x == eid for _, x in p)})
        return shown, e["en"], e["he"], examples


def _item_h(item):
    return THEME_H if item[0] == "theme" else ENTRY_H


def _balance_last(pages, capacity):
    """If the final page uses only column 1, split it across both columns."""
    if not pages:
        return pages
    page = pages[-1]
    if page[1] or len(page[0]) < 8:
        return pages

    items = page[0]
    best = None
    for i in range(4, len(items) - 3):
        if items[i - 1][0] == "theme":       # never end a column on a heading
            continue
        col1, col2 = items[:i], items[i:]
        h1 = sum(_item_h(x) for x in col1)
        h2 = sum(_item_h(x) for x in col2)
        need_head = col2[0][0] != "theme"
        if need_head:
            h2 += THEME_H
        if h1 > capacity or h2 > capacity:
            continue
        score = abs(h1 - h2)
        if best is None or score < best[0]:
            best = (score, i, need_head)
    if best is None:
        return pages

    _, i, need_head = best
    col1, col2 = items[:i], items[i:]
    if need_head:
        theme = "Index"
        for kind, val in reversed(col1):
            if kind == "theme":
                theme = val.replace(" (continued)", "")
                break
        col2 = [("theme", f"{theme} (continued)")] + col2
    pages[-1] = [col1, col2]
    return pages


def glossary_pages(etym, capacity=700.0):
    """Themed index, flowed down two columns.

    One row per surface form, alphabetical inside a theme.  Returns pages ->
    [column 0 items, column 1 items].  A theme heading is never orphaned, and a
    theme that continues in the next column or page repeats its heading with
    "(continued)".
    """
    rows = etym.form_rows()
    items = []
    for theme in etym.themes:
        group = [r for r in rows if r["theme"] == theme]
        group.sort(key=lambda r: (r["key"], r["shown"]))
        if not group:
            continue
        items.append(("theme", theme))
        for r in group:
            items.append(("entry", (r["shown"], r["en"], r["he"], [])))

    pages, page = [], [[], []]
    col, used, cur_theme = 0, 0.0, None

    for item in items:
        kind = item[0]
        h = THEME_H if kind == "theme" else ENTRY_H

        if used + h > capacity:
            carry = None
            if page[col] and page[col][-1][0] == "theme":
                carry = page[col].pop()           # never orphan a heading
            if col == 0:
                col, used = 1, 0.0
            else:
                pages.append(page)
                page, col, used = [[], []], 0, 0.0
            if carry:
                page[col].append(carry)
                used = THEME_H
            elif kind == "entry":                 # re-state the theme
                page[col].append(("theme", f"{cur_theme} (continued)"))
                used = THEME_H

        if kind == "theme":
            cur_theme = item[1]
        page[col].append(item)
        used += h

    if page[0] or page[1]:
        pages.append(page)
    return _balance_last(pages, capacity)
