import json, time, urllib.parse, urllib.request
raw = json.load(open("data/israel_birds_raw.json", encoding="utf-8"))
missing = json.load(open("data/hebrew_missing.json", encoding="utf-8"))
names = json.load(open("data/hebrew_names.json", encoding="utf-8"))
UA = "IsraelBirdSheets/1.0 (personal study project)"

def he_search(term):
    data = urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "list": "search", "srsearch": term, "srlimit": "3"}).encode()
    req = urllib.request.Request("https://he.wikipedia.org/w/api.php", data=data,
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return [h["title"] for h in json.load(r)["query"]["search"]]

for en_title in missing:
    rec = next(r for r in raw if r["en_title"] == en_title)
    hits = he_search(rec["latin"])
    print(f"{rec['latin']:24} ({en_title}) -> {hits}")
    if hits:
        names[en_title] = hits[0]
    time.sleep(1)

json.dump(names, open("data/hebrew_names.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
