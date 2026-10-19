"""Fonts for the pocket edition.

ReportLab caches a TrueType face by its internal PostScript name.  Instancing
NotoSansMono at wght=700 leaves that name as "NotoSansMono-Regular", so a bold
registration silently aliases to the regular face.  Rename the instance before
registering it; the result is a genuinely bold companion with its own face.
"""

import os
import tempfile

import make_book as mb
from fontTools.ttLib import TTFont as FTFont
from fontTools.varLib.instancer import instantiateVariableFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

RENAMES = {
    1: "Noto Sans Mono",
    2: "Bold",
    4: "Noto Sans Mono Bold",
    6: "NotoSansMono-Bold",
    16: "Noto Sans Mono",
    17: "Bold",
}


def bold_face(latin_path):
    f = FTFont(latin_path)
    if "fvar" not in f:
        for cand in (latin_path.replace("-Regular", "-Bold"),
                     latin_path.replace(".ttf", "-Bold.ttf")):
            if os.path.exists(cand):
                return cand
        return None

    inst = instantiateVariableFont(f, {"wght": 700})
    for rec in inst["name"].names:
        if rec.nameID in RENAMES:
            rec.string = RENAMES[rec.nameID].encode(rec.getEncoding())
    fd, out = tempfile.mkstemp(suffix=".ttf", prefix="BirdMonoBold-")
    os.close(fd)
    inst.save(out)
    return out


def register():
    latin = mb.pick(mb.LATIN_CANDIDATES, "Latin")
    hebrew = mb.pick(mb.HEBREW_CANDIDATES, "Hebrew")
    for name, path in (("BirdLatin", latin), ("BirdHebrew", hebrew)):
        pdfmetrics.registerFont(TTFont(name, path))
    bold = hebrew.replace("-Regular", "-Bold")
    pdfmetrics.registerFont(TTFont("BirdHebrewBold",
                                   bold if os.path.exists(bold) else hebrew))
    pdfmetrics.registerFont(TTFont("BirdLatinBold", bold_face(latin)))
    return latin, hebrew
