import json, sys
for p in sys.argv[1:]:
    g = json.load(open(p))
    nodes = g["nodes"]; edges = g["edges"]
    if isinstance(nodes, dict): nodes = [dict(v, id=k) for k, v in nodes.items()]
    nb = {}
    for e in (edges.values() if isinstance(edges, dict) else edges):
        u, v = e.get("u", e.get("from", e.get("source"))), e.get("v", e.get("to", e.get("target")))
        if u is None or v is None: raise SystemExit("edge keys: %s" % list(e))
        nb.setdefault(u, set()).add(v); nb.setdefault(v, set()).add(u)
    w = {n["id"] for n in nodes if n.get("waitable")}
    d = {n["id"] for n in nodes if len(nb.get(n["id"], ())) == 1}
    print(p.split("/")[-2], "waitable", len(w), "deadend", len(d), "exact", w == d, "w-d", len(w-d), "d-w", len(d-w))
