"""Map each species to its Hebrew Wikipedia article title (== the Hebrew bird name)."""
import json, sys, time, urllib.parse, urllib.request

recs = json.load(open("data/israel_birds_raw.json", encoding="utf-8"))
titles = sorted({r["en_title"] for r in recs})
API = "https://en.wikipedia.org/w/api.php"
UA = "IsraelBirdSheets/1.0 (personal study project)"

def fetch(batch):
    data = urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "prop": "langlinks", "lllang": "he", "lllimit": "500",
        "redirects": "1", "titles": "|".join(batch),
    }).encode()
    req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["query"]

result, B = {}, 50
for i in range(0, len(titles), B):
    batch = titles[i:i + B]
    for attempt in range(4):
        try:
            q = fetch(batch)
            break
        except Exception as e:
            print(f"  batch {i}: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
    else:
        continue
    norm = {}
    for n in q.get("normalized", []):
        norm[n["from"]] = n["to"]
    redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
    for page in q.get("pages", []):
        title = page.get("title")
        ll = (page.get("langlinks") or [{}])[0].get("title")
        if ll:
            result[title] = ll
    # map the titles we asked for back through normalize+redirect
    for t in batch:
        t2 = norm.get(t, t)
        t2 = redir.get(t2, t2)
        if t2 in result:
            result.setdefault(t, result[t2])
    print(f"  ...{min(i+B, len(titles))}/{len(titles)} mapped={len(result)}", file=sys.stderr)
    time.sleep(0.5)

json.dump(result, open("data/hebrew_names.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
missing = [t for t in titles if t not in result]
print(f"\nmapped {len(result)}/{len(titles)}; missing {len(missing)}", file=sys.stderr)
json.dump(missing, open("data/hebrew_missing.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("missing sample:", missing[:15], file=sys.stderr)
