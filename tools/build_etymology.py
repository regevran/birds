#!/usr/bin/env python3
"""Build data/etymology.json from the reviewable source data/etymology.md.

The Markdown file is authoritative.  This script refuses to produce a PDF
dataset unless:

  1. every genus and epithet in the species data appears exactly once;
  2. every split reassembles to the exact name;
  3. every segment of a split matches a form in the Elements table;
  4. no whole word begins or ends with a known element unless the line is
     marked `# checked` (this is what catches a missed -ensis);
  5. every element has a valid theme and is actually used.

Run:
    python3 tools/build_etymology.py            # build
    python3 tools/build_etymology.py --check    # report candidates only
"""

import argparse
import json
import os
import re

MD = "data/etymology.md"
THEME_ORDER = [
    "Colour", "Body", "Size", "Shape", "Qualities", "Where it lives",
    "Food", "Behaviour", "Birds", "Mammals", "Other animals",
    "Places", "Word-building",
]


def parse_md(path):
    words = []          # (word, split, checked, lineno)
    elements = []       # (forms, en, he, origin, theme, lineno)
    section = None
    for n, raw in enumerate(open(path, encoding="utf-8"), start=1):
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if not line or line.startswith("#") or line.startswith("### "):
            continue
        if line.startswith("`"):        # the column-legend line
            continue
        body, _, comment = line.partition(" # ")
        if section == "Words":
            if "=" not in body:
                continue
            word, _, split = body.partition("=")
            words.append((word.strip(), split.strip(), comment.strip(), n))
        elif section == "Elements":
            if "|" not in body:
                continue
            f = [x.strip() for x in body.split("|")]
            if len(f) != 5:
                raise SystemExit(f"line {n}: expected 5 fields, got {len(f)}")
            elements.append((f[0], f[1], f[2], f[3], f[4], n))
    return words, elements


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report missed-split candidates without writing")
    args = ap.parse_args()

    records = json.load(open("data/israel_birds_final.json", encoding="utf-8"))
    genera = {r["genus"] for r in records}
    epithets = {r["epithet"] for r in records}
    known = genera | epithets

    words, elements = parse_md(MD)
    errors = []
    candidates = []

    # ---- elements -------------------------------------------------------
    form_map = {}
    elem = {}
    for forms, en, he, origin, theme, n in elements:
        names = [x.strip().lower() for x in forms.split(",") if x.strip()]
        if not names:
            errors.append(f"line {n}: element with no forms")
            continue
        if theme not in THEME_ORDER:
            errors.append(f"line {n}: unknown theme {theme!r}")
        for form in names:
            if form in form_map:
                errors.append(f"line {n}: form {form!r} already maps to "
                              f"{form_map[form]}")
            form_map[form] = names[0]
        elem[names[0]] = dict(forms=names, en=en, he=he, origin=origin,
                              theme=theme, display=names[0])

    # ---- words ----------------------------------------------------------
    seen = {}
    splits = {}
    for word, split, comment, n in words:
        if word in seen:
            errors.append(f"line {n}: {word!r} already on line {seen[word]}")
        seen[word] = n
        if word not in known:
            errors.append(f"line {n}: {word!r} is not in the species data")
            continue

        if split.replace("·", "") != word:
            errors.append(f"line {n}: {word!r} != {split!r} with dots removed")
            continue

        if "·" in split:
            parts = []
            for seg in split.split("·"):
                eid = form_map.get(seg.lower())
                if eid is None:
                    errors.append(f"line {n}: segment {seg!r} of {word!r} "
                                  f"matches no element form")
                parts.append([seg, eid])
            splits[word] = parts
        else:
            splits[word] = None
            if not comment.startswith("checked"):
                candidates.append((word, n))

    for word in sorted(known - seen.keys()):
        errors.append(f"missing from {MD}: {word}")

    used = {eid for parts in splits.values() if parts for _, eid in parts}
    for eid in sorted(elem.keys() - used):
        errors.append(f"element never used: {eid}")

    # ---- missed-split scan ---------------------------------------------
    forms_by_len = sorted(form_map, key=len, reverse=True)
    report = []
    for word, n in candidates:
        low = word.lower()
        hit = None
        for form in forms_by_len:                 # longest match wins
            if len(form) < 3 or form == low:
                continue
            if low.endswith(form) and len(low) - len(form) >= 2:
                hit = ("ends with", form)
                break
            if low.startswith(form) and len(low) - len(form) >= 3:
                hit = ("starts with", form)
                break
        if hit:
            report.append((word, hit[0], hit[1],
                           form_map[hit[1]], n))

    if errors:
        print(f"{len(errors)} error(s):")
        for e in errors[:60]:
            print("  " + e)
        raise SystemExit(1)

    if report:
        print(f"{len(report)} whole word(s) contain a known element but are "
              f"not split or marked '# checked':")
        for word, how, form, eid, n in sorted(report):
            print(f"  line {n:4d}  {word:28s} {how} {form!r} -> {eid}")
        if not args.check:
            print("\nFix these in data/etymology.md (split, or add '# checked').")
            raise SystemExit(1)
        return
    if args.check:
        print("No missed-split candidates: every whole word is accounted for.")

    payload = {
        "elements": {eid: {"en": e["en"], "he": e["he"],
                           "origin": e["origin"], "theme": e["theme"],
                           "display": e["display"], "forms": e["forms"]}
                     for eid, e in elem.items()},
        "splits": {w: p for w, p in splits.items() if p},
        "themes": THEME_ORDER,
    }
    with open("data/etymology.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"Wrote data/etymology.json")
    print(f"  {len(elem)} elements, {len(payload['splits'])} split words, "
          f"{len(words) - len(payload['splits'])} whole")
    print(f"  coverage: {len(seen)} words, all present exactly once")


if __name__ == "__main__":
    main()
