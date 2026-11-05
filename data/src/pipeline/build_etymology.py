#!/usr/bin/env python3
"""Build build/data/etymology.json from reviewable data/in/etymology.md.

The Markdown file is authoritative.  This script refuses to produce a PDF
dataset unless:

  1. every genus and epithet in the species data appears exactly once;
  2. every split reassembles to the exact name;
  3. every segment of a split matches a form in the Elements table;
  4. no whole word begins or ends with a known element unless it is exactly a
     form (which is auto-split) or the line is marked `# checked` (this is what
     catches a missed -ensis);
  5. every element has a valid theme and is used, and every listed form is
     used.

Run:
    python3 data/src/pipeline/build_etymology.py            # build
    python3 data/src/pipeline/build_etymology.py --check    # report candidates only
"""

import argparse
import json
import os
import re

import data_paths

MD = data_paths.ETYMOLOGY_MD
THEME_ORDER = [
    "Colour", "Body", "Size", "Shape", "Qualities", "Where it lives",
    "Food", "Behaviour", "Birds", "Mammals", "Other animals",
    "Places", "Word-building",
]


def parse_md(path):
    words = []          # (word, split, checked, lineno)
    elements = []       # (forms, en, he, origin, theme, lineno)
    whole_names = []    # (word, en, he, source, lineno)
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
        elif section == "Whole names":
            if "|" not in body:
                continue
            f = [x.strip() for x in body.split("|")]
            if len(f) != 4:
                raise SystemExit(f"line {n}: expected 4 fields, got {len(f)}")
            whole_names.append((f[0], f[1], f[2], f[3], n))
    return words, elements, whole_names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report missed-split candidates without writing")
    args = ap.parse_args()

    records = json.load(open(data_paths.BIRDS_FINAL, encoding="utf-8"))
    genera = {r["genus"] for r in records}
    epithets = {r["epithet"] for r in records}
    known = genera | epithets

    words, elements, whole_names = parse_md(MD)
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
        elif word.lower() in form_map:
            # A whole word that is exactly an element form is still a split:
            # it must be set grey and indexed like any other occurrence.
            splits[word] = [[word, form_map[word.lower()]]]
        else:
            splits[word] = None
            if not comment.startswith("checked"):
                candidates.append((word, n))

    for word in sorted(known - seen.keys()):
        errors.append(f"missing from {MD}: {word}")

    used = {eid for parts in splits.values() if parts for _, eid in parts}
    for eid in sorted(elem.keys() - used):
        errors.append(f"element never used: {eid}")
    used_forms = {(seg.lower(), eid)
                  for parts in splits.values() if parts
                  for seg, eid in parts}
    for eid, e in elem.items():
        for form in e["forms"]:
            if (form, eid) not in used_forms:
                errors.append(f"form never used: {form!r} ({eid})")

    whole = {}
    for word, en, he, source, n in whole_names:
        if word not in known:
            errors.append(f"line {n}: whole name {word!r} is not in the "
                          f"species data")
            continue
        if word in whole:
            errors.append(f"line {n}: whole name {word!r} is duplicated")
        if splits.get(word) is not None:
            errors.append(f"line {n}: whole name {word!r} is already split")
        if not en or not he or not source:
            errors.append(f"line {n}: whole name {word!r} needs English, "
                          f"Hebrew and source")
        whole[word] = {"en": en, "he": he, "source": source}

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
            print("\nFix these in data/in/etymology.md (split, or add '# checked').")
            raise SystemExit(1)
        return
    if args.check:
        print("No missed-split candidates: every whole word is accounted for.")
        return

    payload = {
        "elements": {eid: {"en": e["en"], "he": e["he"],
                           "origin": e["origin"], "theme": e["theme"],
                           "display": e["display"], "forms": e["forms"]}
                     for eid, e in elem.items()},
        "splits": {w: p for w, p in splits.items() if p},
        "whole_names": whole,
        "themes": THEME_ORDER,
    }
    with open(data_paths.ETYMOLOGY_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"Wrote {data_paths.ETYMOLOGY_JSON}")
    print(f"  {len(elem)} elements, {len(payload['splits'])} split words, "
          f"{len(words) - len(payload['splits'])} whole, "
          f"{len(whole)} whole-name entries")
    print(f"  coverage: {len(seen)} words, all present exactly once")


if __name__ == "__main__":
    main()
