#!/usr/bin/env python3
"""Per-file rebuilt-vs-archive sha256 table for rebuilt project events.

usage: covariate_hash_table.py FIT_COVERAGE.json OUT.csv WORKSPACE_REGIONS_DIR [...]
Archive hashes come from research/next-combined/canonical-coverage-owner-ab7fda8d/FIT_COVERAGE.json (the owner-archive
manifest). Every archive entry for a rebuilt event is listed: match yes/no, or MISSING if the stage produced no file.
"""
import csv, hashlib, json, os, sys

cov, out, dirs = sys.argv[1], sys.argv[2], sys.argv[3:]
ref = {}
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(k, str) and '/regions/' in k and isinstance(v, str) and len(v) == 64:
                ev, rel = k.split('/regions/', 1)[1].split('/', 1)
                ref[(ev, rel)] = v
            walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(json.load(open(cov)))
rows = []
events = sorted({ev for d in dirs for ev in os.listdir(d)})
for ev in events:
    keys = sorted(rel for (e, rel) in ref if e == ev)
    if not keys: continue
    for rel in keys:
        paths = [os.path.join(d, ev, rel) for d in dirs if os.path.exists(os.path.join(d, ev, rel))]
        got = hashlib.sha256(open(paths[0], 'rb').read()).hexdigest() if paths else ''
        rows.append(dict(event=ev, channel_file=rel, rebuilt_sha256=got, archive_sha256=ref[(ev, rel)],
                         match='MISSING' if not got else ('yes' if got == ref[(ev, rel)] else 'no')))
with open(out, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
from collections import Counter
for ev in sorted({r['event'] for r in rows}):
    print(ev, dict(Counter(r['match'] for r in rows if r['event'] == ev)))
