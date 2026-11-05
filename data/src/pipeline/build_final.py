"""Assemble the final dataset: species + Hebrew names + Hebrew family names."""
import json, collections

import data_paths

merged = json.load(open(data_paths.BIRDS_MERGED, encoding="utf-8"))
fam_he = json.load(open(data_paths.FAMILY_HEBREW, encoding="utf-8"))

# The Hebrew Wikipedia article for a family sometimes redirects to the *genus*
# article (e.g. Phylloscopidae -> עלווית = Phylloscopus), which is not a family
# name, and for several small families no Hebrew family article exists at all.
# An automated "pick the title ending in yod-yod-mem" pass produced wrong answers
# (Dicruridae -> זהבניים, the oriole family), so these are left blank and flagged
# rather than guessed. The page prints the Latin family name instead.
FAMILY_UNVERIFIED = {
    "Dicruridae", "Dromadidae", "Fregatidae", "Hypocoliidae", "Panuridae",
    "Phylloscopidae", "Psittaculidae", "Scotocercidae", "Upupidae",
    "Gaviidae", "Pandionidae", "Regulidae", "Tichodromidae",
}
for fam in FAMILY_UNVERIFIED:
    fam_he.pop(fam, None)

# Verified directly on he.wikipedia: Emberizidae -> "\u05d2\u05d9\u05d1\u05ea\u05d5\u05e0\u05d9\u05d9\u05dd"
FAMILY_OVERRIDE = {"Emberizidae": "\u05d2\u05d9\u05d1\u05ea\u05d5\u05e0\u05d9\u05d9\u05dd"}
fam_he.update(FAMILY_OVERRIDE)

# defensive: never let a Wikipedia disambiguator reach the page
import re as _re
for _f, _v in list(fam_he.items()):
    fam_he[_f] = _re.sub(r"\s*\([^)]*\)\s*$", "", _v).strip()

# Family rank: first appearance in the source checklist defines the order.
family_order = {}
for r in merged:
    family_order.setdefault(r["family"], len(family_order) + 1)

out = []
for r in merged:
    rec = {
        "latin": r["latin"],
        "genus": r["genus"],
        "epithet": r["epithet"],
        "english": r["english"],
        "family": r["family"],
        "family_order": family_order[r["family"]],
        "family_he": fam_he.get(r["family"], ""),
        "order": r["order"],
        "status": r["status"],
        "hebrew": r["hebrew"],
    }
    flags = list(r["flags"])
    if not rec["family_he"]:
        flags.append("no-family-hebrew")
    if r["family"] in FAMILY_UNVERIFIED:
        flags.append("family-hebrew-unverified")
    rec["flags"] = flags
    out.append(rec)

out.sort(key=lambda r: (r["genus"], r["latin"]))
json.dump(out, open(data_paths.BIRDS_FINAL, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("species           :", len(out))
print("genera            :", len({r['genus'] for r in out}))
print("families          :", len({r['family'] for r in out}))
print("with hebrew name  :", sum(1 for r in out if r['hebrew']))
print("with family hebrew:", sum(1 for r in out if r['family_he']))
print("missing hebrew    :")
for r in out:
    if not r["hebrew"]:
        print(f"    {r['latin']:24} {r['english']:26} family={r['family']} status={r['status'] or 'regular'}")
print("families lacking hebrew:",
      sorted({r['family'] for r in out if not r['family_he']}))
print("\nstatus spread     :", dict(collections.Counter(r['status'] or 'regular' for r in out)))
