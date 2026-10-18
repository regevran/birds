import json, sys

d = json.load(open("/tmp/out_backend-api_share_6ad10685-64cc-83eb-b826-bab71f92ee5e.json"))
print("top keys:", list(d.keys())[:40], file=sys.stderr)
print("title:", d.get("title"), file=sys.stderr)

mapping = d.get("mapping") or {}
nodes = [n for n in mapping.values() if n.get("message")]
print("nodes:", len(nodes), file=sys.stderr)

def order(nodes):
    # build parent->child chain starting from a node with no parent
    by_id = {n["id"]: n for n in nodes}
    child_of = {}
    for n in nodes:
        p = n.get("parent")
        if p:
            child_of.setdefault(p, []).append(n["id"])
    roots = [n["id"] for n in nodes if not n.get("parent") or n.get("parent") not in by_id]
    seq, seen = [], set()
    def walk(i):
        if i in seen: return
        seen.add(i)
        if i in by_id: seq.append(i)
        for c in child_of.get(i, []):
            walk(c)
    for r in sorted(roots):
        walk(r)
    return [by_id[i] for i in seq]

out = []
for n in order(nodes):
    m = n["message"]
    role = (m.get("author") or {}).get("role", "?")
    content = m.get("content") or {}
    ctype = content.get("content_type")
    parts = content.get("parts") or []
    text = "\n".join(p if isinstance(p, str) else json.dumps(p) for p in parts)
    if not text.strip() and content.get("text"):
        text = content["text"]
    out.append((role, ctype, text, m.get("create_time")))

with open("/home/ran/dev/ran/birds/data/conversation.txt", "w") as f:
    for i, (role, ctype, text, t) in enumerate(out):
        f.write(f"\n{'='*70}\n[{i}] {role.upper()}  ({ctype})\n{'='*70}\n{text}\n")

for i, (role, ctype, text, t) in enumerate(out):
    print(f"--- [{i}] {role} ({ctype}) len={len(text)} ---")
    print(text[:400].replace("\n", " ")[:400])
