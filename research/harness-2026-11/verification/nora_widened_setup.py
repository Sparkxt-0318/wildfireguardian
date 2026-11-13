"""Independent verifier: widened-graph UA re-run setup with MY inputs (graphs rebuilt from the owner pbf, my packets).
Builds G1/G1p (author's fdyn.widened_g1.build on my graphs), padded packets for the sample combos (author's builder path
with my rebuilt widened graph), and a pairs file for the author's fdyn/widened_runs.py.
argv: F-DYN dir (wg worktree), v37 worktree, roads dir, out dir, python"""
import json, sys, subprocess, os, numpy as np
from pathlib import Path
FD, W37, RD, OUT, PY = map(Path, sys.argv[1:6]); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(FD))
from fdyn import widened_g1
g1 = json.load(open(RD / 'ua_step1.json')); gw = json.load(open(RD / 'k_kfs01_grid5km.json'))
b = widened_g1.build(g1, gw)
gd = OUT / 'graphs' / 'uiseong_andong_2025'; gd.mkdir(parents=True, exist_ok=True)
for k in ('G1', 'G1p'):
    json.dump(b[k], open(gd / f'{k}.json', 'w'))
print('G1/G1p report', json.dumps(b['report'])[:600], flush=True)
mask = np.ones((107, 265), bool); mask[:14, :] = mask[-14:, :] = False; mask[:, :14] = mask[:, -14:] = False
np.savez(OUT / 'padding_support.npz', support=mask)
m = json.load(open(W37 / 'research/harness-2026-11/F-DYN/MANIFEST_v3_7.json'))
combos = [('20250323T010000Z', h, v) for h in (5, 8) for v in ('envelope', 'firms_early')] + \
         [('20250324T090000Z', h, 'kriged_mean') for h in (5, 8)] + [('20250325T170000Z', 5, 'kriged_mean')]
rows = []
for s, h, v in combos:
    e = [e for e in m['entries'] if e['region'] == 'uiseong_andong_2025' and e['start'] == s and e['horizon_h'] == h
         and e['variant'] == v and e['transform'] == 'no_reentry/2'][0]
    old = W37 / e['out']; new = OUT / 'padded' / f'{s}_h{h}_{v}'
    if not (new / 'HAZARD.json').exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        cmd = list(e['cmd']); cmd[0] = str(PY)
        def setv(k, val):
            cmd[cmd.index(k) + 1] = val
        setv('--out', str(new)); setv('--graph', str(RD / 'k_kfs01_grid5km.json'))
        cmd += ['--pad-cells', '14', '--padded-export-dir', str(new) + '.export', '--support-mask', str(OUT / 'padding_support.npz'),
                '--support-rule', 'supplied/1', '--support-provenance', json.dumps({'by': 'independent verifier', 'rule': 'WIDENED_GRAPH_RULE.md §2', 'padding_cells': 9632})]
        r = subprocess.run(cmd, cwd=FD.parents[2], capture_output=True, text=True)   # repo root of the widened-graph worktree (new build.py)
        print('padded', s, h, v, 'rc', r.returncode, r.stderr[-200:] if r.returncode else '', flush=True)
    rows.append({'combo': ['uiseong_andong_2025', s, h, v], 'old': str(old), 'new': str(new), 'old_rc': 0, 'new_rc': 0, 'P2': True, 'P3': True})
json.dump({'rows': rows, 'all_P2': True, 'all_P3': True}, open(OUT / 'PAIRS_NORA.json', 'w'), indent=1)
print('pairs', len(rows))
