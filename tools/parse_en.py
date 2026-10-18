import re, html, sys, json
s = open("data/raw/en_israel.html", encoding="utf-8", errors="replace").read()
# strip tags of the content area
body = s
tables = re.findall(r'<table.*?</table>', body, re.S)
print("tables:", len(tables), file=sys.stderr)
rows_total = 0
sample = []
for t in tables:
    rows = re.findall(r'<tr.*?</tr>', t, re.S)
    for r in rows:
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)
        clean = [html.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in cells]
        clean = [c for c in clean if c]
        if clean:
            rows_total += 1
            if len(sample) < 25:
                sample.append(clean)
print("rows:", rows_total, file=sys.stderr)
for s_ in sample:
    print(json.dumps(s_, ensure_ascii=False))
