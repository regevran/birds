import json, sys, time, urllib.parse, urllib.request
missing = json.load(open("data/hebrew_missing.json", encoding="utf-8"))
result = json.load(open("data/hebrew_names.json", encoding="utf-8"))
missing = [t for t in missing if t not in result]
print(f"to retry: {len(missing)}", file=sys.stderr)
API = "https://en.wikipedia.org/w/api.php"
UA = "IsraelBirdSheets/1.0 (personal study project)"

def fetch(batch):
    data = urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "prop": "langlinks", "lllang": "he", "lllimit": "500",
        "redirects": "1", "titles": "|".join(batch)}).encode()
    req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["query"]

for i in range(0, len(missing), 10):
    batch = missing[i:i+10]
    for attempt in range(6):
        try:
            q = fetch(batch); break
        except Exception as e:
            print(f"  retry {attempt}: {e}", file=sys.stderr); time.sleep(5 * (attempt + 1))
    else:
        continue
    norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
    redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
    bytitle = {}
    for page in q.get("pages", []):
        ll = (page.get("langlinks") or [{}])[0].get("title")
        if ll: bytitle[page.get("title")] = ll
    for t in batch:
        t2 = norm.get(t, t); t2 = redir.get(t2, t2)
        if t2 in bytitle: result[t] = bytitle[t2]
    time.sleep(2)

json.dump(result, open("data/hebrew_names.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
still = [t for t in missing if t not in result]
print(f"now mapped {len(result)}; still missing {len(still)}", file=sys.stderr)
json.dump(still, open("data/hebrew_missing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
