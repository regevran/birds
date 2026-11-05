#!/usr/bin/env python3
"""One-off triage of the detector's candidate list.

Applies the splits that are real and extends element forms where a root was
listed only in one surface form.  Run after this: build_etymology.py --check
lists whatever still needs '# checked'.
"""

import os
import re
import sys

MD = "data/etymology.md"

SPLITS = {
    # place + -ensis
    "capensis": "cap·ensis",
    "bengalensis": "bengal·ensis",
    "benghalensis": "benghal·ensis",
    "chinensis": "chin·ensis",
    "hispaniolensis": "hispaniol·ensis",
    "madagascariensis": "madagascari·ensis",
    "nipalensis": "nipal·ensis",
    "pratensis": "prat·ensis",
    "sandvicensis": "sandvic·ensis",
    "senegalensis": "senegal·ensis",
    "smyrnensis": "smyrn·ensis",
    "zeylonensis": "zeylon·ensis",
    # root + -atus / -ata
    "barbatus": "barb·atus",
    "conspicillata": "conspicill·ata",
    "coronatus": "coron·atus",
    "cristata": "crist·ata",
    "cristatus": "crist·atus",
    "fasciata": "fasci·ata",
    "fuscatus": "fusc·atus",
    "inornatus": "inorn·atus",
    "lobatus": "lob·atus",
    "optatus": "opt·atus",
    "pennatus": "penn·atus",
    "signata": "sign·ata",
    "stellata": "stell·ata",
    "striata": "stri·ata",
    "striolata": "striol·ata",
    "torquatus": "torqu·atus",
    "caligata": "calig·ata",
    "clypeata": "clype·ata",
    # other suffixes already in the index
    "spinosus": "spin·osus",
    "Gulosus": "Gul·osus",
    "scirpaceus": "scirp·aceus",
    "scolopaceus": "scolop·aceus",
    "fluviatilis": "fluvi·atilis",
    "stagnatilis": "stagn·atilis",
    "riparia": "rip·aria",
    "muraria": "mur·aria",
    "nebularia": "nebul·aria",
    "apricaria": "apric·aria",
    "Linaria": "Lin·aria",
    "albellus": "alb·ellus",
    "citrinella": "citrin·ella",
    "rufula": "ruf·ula",
    "citreola": "citre·ola",
    "aureola": "aure·ola",
    "glareola": "glare·ola",
    "ralloides": "rall·oides",
    "falcinellus": "falcin·ellus",
    "ardeola": "Arde·ola",
    # compounds
    "dactylatra": "dactyl·atra",
    "viscivorus": "visci·vorus",
    "coccothraustes": "cocco·thraustes",
    "gallinago": "gallin·ago",
    "troglodytes": "trogl·odytes",
    # genera of the same words
    "Coracias": "Corac·ias",
    "Riparia": "Rip·aria",
}

# forms to add to an existing element, keyed by any form already on its line;
# the optional second value becomes the display form (first in the list)
FORM_ADD = {
    "albi": (["alb", "alba"], "alb"),
    "atri": (["ater", "atra"], "ater"),
    "corax": (["corac"], None),
    "dactyla": (["dactyl"], "dactyl"),
    "fusci": (["fusc", "fusca"], "fusc"),
    "gularis": (["gul"], "gul"),
    "maculata": (["macul"], "macul"),
    "pratin": (["prat"], "prat"),
    "rufi": (["ruf", "rufa"], "ruf"),
    "squami": (["squam"], "squam"),
}

NEW_ELEMENTS = [
    # forms | English | Hebrew | origin | theme
    ("bengal, benghal", "Bengal", "בנגל", "place name", "Places and people"),
    ("cap", "the Cape", "כף התקווה הטובה", "place name", "Places and people"),
    ("chin", "China", "סין", "place name", "Places and people"),
    ("hispaniol", "Hispaniola", "היספניולה", "place name", "Places and people"),
    ("madagascari", "Madagascar", "מדגסקר", "place name", "Places and people"),
    ("nipal", "Nepal", "נפאל", "place name", "Places and people"),
    ("sandvic", "the Sandwich Islands", "איי סנדוויץ", "place name", "Places and people"),
    ("senegal", "Senegal", "סנגל", "place name", "Places and people"),
    ("smyrn", "Smyrna", "סמירנה", "place name", "Places and people"),
    ("zeylon", "Ceylon", "ציילון", "place name", "Places and people"),

    ("aure", "golden", "זהוב", "Latin", "Colour"),
    ("citre", "citron-yellow", "צהוב אתרוג", "Latin", "Colour"),
    ("citrin", "lemon-yellow", "צהוב לימון", "Latin", "Colour"),
    ("fasci", "band", "פס", "Latin", "Colour"),
    ("inorn", "unadorned", "חסר קישוט", "Latin", "Colour"),
    ("sign", "mark", "סימן", "Latin", "Colour"),
    ("stell", "star", "כוכב", "Latin", "Colour"),
    ("stri", "stripe", "פס", "Latin", "Colour"),

    ("barb", "beard", "זקן", "Latin", "Body"),
    ("conspicill", "spectacles", "משקפיים", "Latin", "Body"),
    ("coron", "crown", "כתר", "Latin", "Body"),
    ("crist", "crest", "ציצית", "Latin", "Body"),
    ("lob", "lobe", "אונה", "Latin", "Body"),
    ("penn", "feather", "נוצה", "Latin", "Body"),
    ("spin", "thorn", "קוץ", "Latin", "Body"),
    ("torqu", "collar", "צווארון", "Latin", "Body"),
    ("calig", "boot", "מגף", "Latin", "Body"),

    ("aprica", "sunny", "שטוף שמש", "Latin", "Where it lives"),
    ("fluvi", "river", "נהר", "Latin", "Where it lives"),
    ("lin", "flax", "פשתן", "Latin", "Where it lives"),
    ("mur", "wall", "חומה", "Latin", "Where it lives"),
    ("nebul", "mist", "ערפל", "Latin", "Where it lives"),
    ("rip", "bank", "גדה", "Latin", "Where it lives"),
    ("scirp", "rush", "אגמון", "Latin", "Where it lives"),
    ("stagn", "pool", "שלולית", "Latin", "Where it lives"),

    ("visci", "mistletoe", "דבקון", "Latin", "Food and behaviour"),

    ("rall", "rail", "רלית", "Latin", "Birds, beasts and people"),
    ("scolop", "snipe", "חרטומן", "Latin", "Birds, beasts and people"),

    ("opt", "wished-for", "רצוי", "Latin", "Size and shape"),
    ("clype", "shield", "מגן", "Latin", "Size and shape"),
    ("falcin", "sickle", "מגל", "Latin", "Size and shape"),
]


def main():
    lines = open(MD, encoding="utf-8").read().splitlines()
    out, section = [], None
    applied = set()
    for raw in lines:
        line = raw
        if line.startswith("## "):
            section = line[3:].strip()
        if section == "Words":
            m = re.match(r"^([A-Za-z]+) = (.*)$", line)
            if m and m.group(1) in SPLITS:
                word = m.group(1)
                line = f"{word} = {SPLITS[word]}"
                applied.add(word)
        out.append(line)

    missing = set(SPLITS) - applied
    if missing:
        raise SystemExit(f"words not found in the file: {sorted(missing)}")

    # rewrite element lines where a form/display is being extended
    start = next(i for i, l in enumerate(out) if l.strip() == "## Elements")
    head, body = out[:start], out[start:]

    rewritten = []
    for line in body:
        if "|" not in line or line.startswith("`"):
            rewritten.append(line)
            continue
        f = [x.strip() for x in line.split("|")]
        if len(f) != 5:
            rewritten.append(line)
            continue
        forms = [x.strip() for x in f[0].split(",") if x.strip()]
        changed = False
        for anchor, (extra, display) in FORM_ADD.items():
            if anchor in forms:
                for e in extra:
                    if e not in forms:
                        forms.append(e)
                if display:
                    forms.remove(display) if display in forms else None
                    forms.insert(0, display)
                changed = True
                break
        rewritten.append(" | ".join([", ".join(forms)] + f[1:]) if changed else line)

    rewritten.append("")
    for forms, en, he, origin, theme in NEW_ELEMENTS:
        rewritten.append(f"{forms} | {en} | {he} | {origin} | {theme}")

    open(MD, "w", encoding="utf-8").write("\n".join(head + rewritten) + "\n")
    print(f"applied {len(applied)} splits, added {len(NEW_ELEMENTS)} elements")


if __name__ == "__main__":
    main()
