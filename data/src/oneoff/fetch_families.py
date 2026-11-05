"""Hebrew names for the bird families, via en.wikipedia -> he.wikipedia langlinks."""
import json, sys, time, urllib.parse, urllib.request

recs = json.load(open("data/israel_birds_merged.json", encoding="utf-8"))
fams = sorted({r["family"] for r in recs if r["family"]})
print(f"families: {len(fams)}", file=sys.stderr)
API, UA = "https://en.wikipedia.org/w/api.php", "IsraelBirdSheets/1.0 (study project)"

def fetch(batch):
    data = urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "prop": "langlinks", "lllang": "he", "lllimit": "500",
        "redirects": "1", "titles": "|".join(batch)}).encode()
    req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["query"]

out = {}
for i in range(0, len(fams), 25):
    batch = fams[i:i + 25]
    for attempt in range(6):
        try:
            q = fetch(batch); break
        except Exception as e:
            print(f"  {e}", file=sys.stderr); time.sleep(4 * (attempt + 1))
    else:
        continue
    norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
    redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
    by = {}
    for p in q.get("pages", []):
        ll = (p.get("langlinks") or [{}])[0].get("title")
        if ll: by[p.get("title")] = ll
    for f in batch:
        t = redir.get(norm.get(f, f), norm.get(f, f))
        if t in by: out[f] = by[t]
    time.sleep(1.5)

json.dump(out, open("data/family_hebrew.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"resolved {len(out)}/{len(fams)}", file=sys.stderr)
print("missing:", [f for f in fams if f not in out], file=sys.stderr)
for f in fams[:10]:
    print(f"   {f:20} {out.get(f,'?')}")
