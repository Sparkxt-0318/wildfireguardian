import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
diffs = []
def walk(x, y, path):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if k not in x or k not in y: diffs.append(path + [k]); continue
            walk(x[k], y[k], path + [k])
    elif isinstance(x, list) and isinstance(y, list):
        if len(x) != len(y): diffs.append(path + ['<len>']); return
        for i, (p, q) in enumerate(zip(x, y)): walk(p, q, path + [i])
    elif x != y:
        diffs.append(path)
    return
walk(a, b, [])
leaf = sorted({str(p[-1]) for p in diffs})
print("differing leaves:", len(diffs), "distinct keys:", leaf)
print("ONLY source differs:", leaf == ['source'])
print("source values (run4):", sorted({json.dumps(b['labels'][k].get('source'), ensure_ascii=False) for k in b['labels']})[:2])
