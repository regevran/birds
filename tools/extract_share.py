import json, re, sys, html

p = "/tmp/chatgpt_share.html"
s = open(p, encoding="utf-8", errors="replace").read()

# 1) Try the react-router streaming context
m = re.search(r'window\.__reactRouterContext\s*=\s*(\{.*?\});</script>', s, re.S)
print("router ctx found:", bool(m), file=sys.stderr)

# 2) Look for linear_conversation / mapping structures anywhere in the page
for key in ["linear_conversation", "serverResponse", "mapping", "Create Israel Bird List"]:
    print(key, s.count(key), file=sys.stderr)

# dump all JSON-ish script payloads to files for inspection
out = []
for i, mm in enumerate(re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', s, re.S)):
    out.append(mm.group(1))
print("json scripts:", len(out), file=sys.stderr)
for i, o in enumerate(out):
    open(f"/tmp/share_json_{i}.json", "w").write(html.unescape(o))
