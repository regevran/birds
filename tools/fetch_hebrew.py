"""Fetch Hebrew names for each taxon from Wikidata (P225 taxon name -> he label / hewiki title)."""
import json, sys, time, urllib.parse, urllib.request

recs = json.load(open("data/israel_birds_raw.json", encoding="utf-8"))
names = sorted({r["latin"] for r in recs})
print(f"unique binomials: {len(names)}", file=sys.stderr)

ENDPOINT = "https://query.wikidata.org/sparql"
UA = "IsraelBirdSheets/1.0 (personal study project; contact: local user)"

def query(batch):
    values = " ".join('"%s"' % n for n in batch)
    q = f"""SELECT ?name ?heLabel ?hewiki WHERE {{
  VALUES ?name {{ {values} }}
  ?taxon wdt:P225 ?name .
  OPTIONAL {{ ?taxon rdfs:label ?heLabel . FILTER(lang(?heLabel) = "he") }}
  OPTIONAL {{ ?hewiki schema:about ?taxon ; schema:isPartOf <https://he.wikipedia.org/> . }}
}}"""
    url = ENDPOINT + "?" + urllib.parse.urlencode({"query": q, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)["results"]["bindings"]

out = {}
B = 80
for i in range(0, len(names), B):
    batch = names[i:i + B]
    for attempt in range(3):
        try:
            rows = query(batch)
            break
        except Exception as e:
            print(f"  batch {i} attempt {attempt+1} failed: {e}", file=sys.stderr)
            time.sleep(3)
    else:
        continue
    for row in rows:
        n = row["name"]["value"]
        he = row.get("heLabel", {}).get("value")
        hew = row.get("hewiki", {}).get("value")
        hew_title = urllib.parse.unquote(hew.rsplit("/", 1)[-1]).replace("_", " ") if hew else None
        d = out.setdefault(n, {})
        if he:
            d["he_label"] = he
        if hew_title:
            d["hewiki"] = hew_title
    print(f"  ...{min(i+B, len(names))}/{len(names)}  resolved={len(out)}", file=sys.stderr)
    time.sleep(1)

json.dump(out, open("data/hebrew_wikidata.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
missing = [n for n in names if n not in out]
print(f"resolved {len(out)}/{len(names)}; missing {len(missing)}", file=sys.stderr)
json.dump(missing, open("data/hebrew_missing.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
