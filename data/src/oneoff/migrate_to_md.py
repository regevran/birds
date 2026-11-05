#!/usr/bin/env python3
"""One-off: turn the Python split tables into the reviewable Markdown source.

After this runs, data/etymology.md is authoritative and etym_data.py is history.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from etym_data import ELEMENTS, SPLITS
from etym_themes import theme_of


def main():
    records = json.load(open("data/israel_birds_final.json", encoding="utf-8"))
    genera = sorted({r["genus"] for r in records})
    epithets = sorted({r["epithet"] for r in records})
    known = set(genera) | set(epithets)

    extra = sorted(set(SPLITS) - known)
    if extra:
        raise SystemExit(f"splits for unknown words: {extra}")

    # forms: every surface actually printed for an element
    forms = {}
    for word, parts in SPLITS.items():
        for surface, eid in parts:
            forms.setdefault(eid, []).append(surface)

    themes = theme_of()
    used = set(forms)
    missing = used - set(ELEMENTS)
    if missing:
        raise SystemExit(f"missing element definitions: {sorted(missing)}")

    out = []
    out.append("# Etymology source\n")
    out.append("This file is the source of truth for how Latin names are split.\n")
    out.append("Words are written `word = split`. A middle dot `·` marks a morpheme")
    out.append("boundary; a word with no dot is deliberately whole. Every segment must")
    out.append("match a form in the Elements table at the bottom.\n")
    out.append("Add `# checked` to a whole-word line to say \"I looked at this and it")
    out.append("is not decomposable\"; the build reports any whole word that ends or")
    out.append("begins with a known element but has not been marked.\n")
    out.append("## Words\n")
    out.append("### Genera\n")
    for word in genera:
        parts = SPLITS.get(word)
        shown = "·".join(s for s, _ in parts) if parts else word
        out.append(f"{word} = {shown}")
    out.append("\n### Epithets\n")
    for word in epithets:
        parts = SPLITS.get(word)
        shown = "·".join(s for s, _ in parts) if parts else word
        out.append(f"{word} = {shown}")

    out.append("\n## Elements\n")
    out.append("`forms | English | Hebrew | origin | theme`")
    out.append("The first form is the one printed in the index.\n")
    for eid in sorted(used, key=lambda e: e.lower()):
        surface = forms[eid]
        # case variants collapse: Chryso and chryso are one form
        unique = {}
        for s in surface:
            unique.setdefault(s.lower(), s)
        ordered = sorted(unique.values(),
                         key=lambda s: (-surface.count(s), -len(s), s.lower()))
        en, he, origin = ELEMENTS[eid]
        out.append(" | ".join([", ".join(ordered), en, he, origin,
                               themes[eid]]))

    os.makedirs("data", exist_ok=True)
    with open("data/etymology.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"Wrote data/etymology.md")
    print(f"  {len(genera)} genera + {len(epithets)} epithets, "
          f"{len(SPLITS)} split, {len(used)} elements")


if __name__ == "__main__":
    main()
