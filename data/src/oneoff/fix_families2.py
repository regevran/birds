"""Resolve Hebrew FAMILY names: prefer a he.wikipedia title ending in the family
suffix 'יים' over the genus article the family page happens to redirect to."""
import json, time, urllib.parse, urllib.request
UA = "IsraelBirdSheets/1.0 (study project)"
TARGETS = ["Dicruridae", "Dromadidae", "Fregatidae", "Hypocoliidae", "Panuridae",
           "Phylloscopidae", "Psittaculidae", "Scotocercidae", "Upupidae",
           "Gaviidae", "Pandionidae", "Regulidae", "Tichodromidae"]

def search(term, limit=8):
    url = "https://he.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "list": "search", "srsearch": term, "srlimit": str(limit)})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return [h["title"] for h in json.load(r)["query"]["search"]]

found = {}
for fam in TARGETS:
    try:
        hits = search(fam)
    except Exception as e:
        print(f"{fam:16} search failed: {e}")
        time.sleep(8)
        continue
    cand = [h for h in hits if h.endswith("יים")]   # ...יים
    pick = cand[0] if cand else None
    found[fam] = pick
    print(f"{fam:16} -> {pick!r:22} (all hits: {hits})")
    time.sleep(8)

json.dump({k: v for k, v in found.items() if v},
          open("data/family_hebrew_fixed.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nresolved:", sum(1 for v in found.values() if v), "/", len(TARGETS))
