import json, time, urllib.parse, urllib.request
UA = "IsraelBirdSheets/1.0 (study project)"

def search(host, term, limit=6):
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "list": "search", "srsearch": term, "srlimit": str(limit)})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return [h["title"] for h in json.load(r)["query"]["search"]]

for fam in ["Emberizidae", "Gaviidae", "Pandionidae"]:
    try:
        hits = search("he.wikipedia.org", fam)
        print(f"{fam:14} -> {hits}")
    except Exception as e:
        print(f"{fam:14} -> error {e}")
    time.sleep(6)
