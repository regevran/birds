import json, time, urllib.parse, urllib.request
UA = "IsraelBirdSheets/1.0 (study project)"
TODO = ["Anhingidae", "Pelecanidae", "Regulidae", "Tichodromidae"]

def api(host, params):
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

out = json.load(open("data/family_hebrew.json", encoding="utf-8"))
for fam in TODO:
    # 1) find the taxon item on Wikidata
    s = api("www.wikidata.org", {"action": "wbsearchentities", "search": fam,
                                 "language": "en", "type": "item", "limit": "5",
                                 "format": "json"})
    qid = None
    for hit in s.get("search", []):
        if hit.get("label", "").lower() == fam.lower() or hit.get("match", {}).get("text", "").lower() == fam.lower():
            qid = hit["id"]; break
    if not qid and s.get("search"):
        qid = s["search"][0]["id"]
    time.sleep(1)
    if not qid:
        print(f"{fam}: no wikidata item"); continue
    # 2) take the Hebrew label
    e = api("www.wikidata.org", {"action": "wbgetentities", "ids": qid,
                                 "props": "labels|descriptions", "languages": "he|en",
                                 "format": "json"})
    ent = e["entities"][qid]
    he = ent.get("labels", {}).get("he", {}).get("value")
    en = ent.get("labels", {}).get("en", {}).get("value")
    print(f"{fam:16} -> {qid}  en={en!r}  he={he!r}")
    if he:
        out[fam] = he
    time.sleep(1)

json.dump(out, open("data/family_hebrew.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("total families with hebrew:", len(out))
