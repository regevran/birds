"""Parse the English Wikipedia 'List of birds of Israel' wikitext into structured JSON."""
import json, re, collections

src = open("data/raw/en_israel.wiki", encoding="utf-8").read()
lines = src.split("\n")

SPECIES_RE = re.compile(r"^\*\s*(.+?),\s*''([A-Z][a-z]+)\s+([a-z][a-z\-]+)''\s*(?:\(([^)]*)\))?\s*$")
LINK_RE = re.compile(r"^\[\[([^\]|]+)")
SECTION_RE = re.compile(r"^==\s*([^=]+?)\s*==\s*$")
ORDER_FAMILY_RE = re.compile(r"Order:\s*\[\[([^\]|]+)(?:\|[^\]]*)?\]\].*?Family:\s*\[\[([^\]|]+)")

records, section, order, family = [], None, None, None
for raw in lines:
    line = raw.strip()
    m = SECTION_RE.match(line)
    if m:
        section = m.group(1)
        order = family = None
        continue
    if section in (None, "Background", "References", "See also", "External links"):
        continue
    m = ORDER_FAMILY_RE.search(line)
    if m:
        order, family = m.group(1).strip(), m.group(2).strip()
        continue
    m = SPECIES_RE.match(line)
    if m:
        common, genus, epithet, status = m.groups()
        lm = LINK_RE.match(common.strip())
        en_title = lm.group(1).strip() if lm else None
        common = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", common)
        common = re.sub(r"\[\[([^\]]+)\]\]", r"\1", common).strip()
        records.append({
            "latin": f"{genus} {epithet}",
            "genus": genus,
            "epithet": epithet,
            "english": common,
            "family": family,
            "order": order,
            "section": section,
            "en_title": en_title,
            "status": (status or "").strip(),
        })

# genus -> family/order should be consistent; report anomalies
gf = collections.defaultdict(set)
for r in records:
    gf[r["genus"]].add((r["order"], r["family"]))
weird = {g: v for g, v in gf.items() if len(v) > 1}

json.dump(records, open("data/israel_birds_raw.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"species parsed : {len(records)}")
print(f"genera         : {len(gf)}")
print(f"families       : {len({r['family'] for r in records})}")
print(f"missing family : {sum(1 for r in records if not r['family'])}")
print(f"genera w/ >1 family: {len(weird)}")
for g, v in list(weird.items())[:8]:
    print(f"   {g}: {sorted(v)}")
print("\nstatus breakdown:")
for k, v in collections.Counter(r["status"] for r in records).most_common():
    print(f"   {k or '(regular)':12} {v}")
print("\nspecies per family (top 12):")
for f, n in collections.Counter(r["family"] for r in records).most_common(12):
    print(f"   {f:22} {n}")
print("\nspecies per genus (top 12):")
gc = collections.Counter(r["genus"] for r in records)
for g, n in gc.most_common(12):
    print(f"   {g:18} {n}")
print(f"\ndistribution of genus sizes:")
for k, v in sorted(collections.Counter(gc.values()).items()):
    print(f"   {k} species: {v} genera")
