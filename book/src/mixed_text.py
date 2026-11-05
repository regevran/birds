"""Draw mixed Hebrew/Latin lines in per-script font runs.

The Hebrew face carries only Hebrew letters, geresh, gershayim and the maqaf.
Digits, ASCII punctuation and Latin names come from the Latin face.  A line is
bidi-reordered with a right-to-left base direction and then split into runs so
each run can use its own font.
"""

from bidi.algorithm import get_display
from reportlab.pdfbase import pdfmetrics

HEB_START, HEB_END = "֐", "׿"


def _is_hebrew(ch):
    return HEB_START <= ch <= HEB_END


def _runs(text, base_dir="R"):
    """Visual-order (font kind, string) runs for one line."""
    if any(_is_hebrew(ch) for ch in text):
        text = get_display(text, base_dir=base_dir)
    runs = []
    for ch in text:
        kind = "he" if _is_hebrew(ch) else "lat"
        if runs and runs[-1][0] == kind:
            runs[-1] = (kind, runs[-1][1] + ch)
        else:
            runs.append((kind, ch))
    return runs


def _fonts(he_bold=False, lat_bold=False):
    return ("BirdHebrewBold" if he_bold else "BirdHebrew",
            "BirdLatinBold" if lat_bold else "BirdLatin")


def rich_width(text, size, he_bold=False, lat_bold=False):
    hf, lf = _fonts(he_bold, lat_bold)
    return sum(pdfmetrics.stringWidth(s, hf if kind == "he" else lf, size)
               for kind, s in _runs(text))


def draw_rich(c, text, size, x, y, align="right", he_bold=False,
              lat_bold=False):
    """Draw one mixed Hebrew/Latin line and return its width."""
    hf, lf = _fonts(he_bold, lat_bold)
    runs = _runs(text)
    total = sum(pdfmetrics.stringWidth(s, hf if kind == "he" else lf, size)
                for kind, s in runs)
    if align == "right":
        cx = x - total
    elif align == "center":
        cx = x - total / 2.0
    else:
        cx = x
    for kind, s in runs:
        font = hf if kind == "he" else lf
        c.setFont(font, size)
        c.drawString(cx, y, s)
        cx += pdfmetrics.stringWidth(s, font, size)
    return total


def wrap_rich(text, size, width, he_bold=False, lat_bold=False):
    """Wrap a mixed line on spaces, measuring the visual (font-run) width.

    A newline in ``text`` is a hard break: each segment wraps on its own.
    """
    out = []
    for hard in text.split("\n"):
        lines, cur = [], ""
        for word in hard.split():
            trial = word if not cur else cur + " " + word
            if cur and rich_width(trial, size, he_bold, lat_bold) > width:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        if cur:
            lines.append(cur)
        out.extend(lines)
    return out


def draw_rich_para(c, text, size, right, y, width, leading=None):
    """Right-aligned mixed-script paragraph; returns the next baseline."""
    leading = leading or size * 1.45
    for line in wrap_rich(text, size, width):
        draw_rich(c, line, size, right, y)
        y -= leading
    return y


def draw_left_para(c, text, size, x, y, width, leading=None):
    """Left-aligned Latin paragraph; returns the next baseline."""
    leading = leading or size * 1.45
    for line in wrap_rich(text, size, width):
        draw_rich(c, line, size, x, y, align="left")
        y -= leading
    return y
