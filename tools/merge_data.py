"""Merge the parsed list with Hebrew names, flag anything that looks untrustworthy."""
import json, re, collections

raw = json.load(open("data/israel_birds_raw.json", encoding="utf-8"))
he = json.load(open("data/hebrew_names.json", encoding="utf-8"))

SUSPECT = re.compile(r"[()\[\]]|סוג|משפחה|שבט")
merged, flags = [], collections.Counter()
for r in raw:
    name = he.get(r["en_title"])
    # strip Wikipedia disambiguators like "לוחם (עוף)" / "תפר (ציפור)"
    if name:
        name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    kinds = []
    if not name:
        kinds.append("no-hebrew")
    elif SUSPECT.search(name):
        kinds.append("suspicious-title")
    elif not re.search(r"[֐-׿]", name):
        kinds.append("no-hebrew-chars")
    elif len(name.split()) > 4:
        kinds.append("long-title")
    for k in kinds:
        flags[k] += 1
    r["hebrew"] = "" if kinds else name
    r["flags"] = kinds
    merged.append(r)

json.dump(merged, open("data/israel_birds_merged.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print("total           :", len(merged))
print("with hebrew     :", sum(1 for r in merged if r["hebrew"]))
print("flagged         :", sum(1 for r in merged if r["flags"]))
print("flag breakdown  :", dict(flags))

print("\n--- spot check: well-known species ---")
by_latin = {r["latin"]: r for r in merged}
for lat in ["Columba livia", "Streptopelia decaocto", "Spilopelia senegalensis",
            "Upupa epops", "Passer domesticus", "Corvus corax", "Anas platyrhynchos",
            "Falco peregrinus", "Turdus merula", "Pycnonotus xanthopygos",
            "Phoenicopterus roseus", "Ciconia ciconia", "Athene noctua"]:
    r = by_latin.get(lat)
    print(f"  {lat:26} {r['hebrew'] if r else 'NOT IN LIST'!s:20} {r['family'] if r else ''}")

print("\n--- flagged rows (all) ---")
for r in merged:
    if r["flags"]:
        print(f"  {r['latin']:26} {r['english']:28} {r['flags']}")
