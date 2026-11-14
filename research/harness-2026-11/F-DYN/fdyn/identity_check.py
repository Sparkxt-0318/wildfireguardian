"""IDENTITY_PATH_RULE.md acceptance (a) and (b).

(a) Build the same MANIFEST_v3_5 entries in two checkouts of one commit at different absolute paths; HAZARD.json,
    REPORT.json, NATIVE_METADATA.json and constructed_arrays.npz must have identical sha256.
(b) Compare each v3.5 packet with its v3.4 counterpart as parsed JSON: the only allowed differences are
    radiation_operator.module and the added module_path_form; npz byte-identical.

    python3 research/harness-2026-11/F-DYN/fdyn/identity_check.py --checkout-b /path/to/other/checkout \
        --only REGION:START:H:VARIANT [...] --out IDENTITY_CHECK.json
Checkout B's --out is redirected to packets_v35_checkoutB/ so both builds can share one _data store.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MAN = REPO / 'research/harness-2026-11/F-DYN/MANIFEST_v3_5.json'
FILES = ('HAZARD.json', 'REPORT.json', 'NATIVE_METADATA.json', 'constructed_arrays.npz')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def diff(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f'{path}/{k}')
            else:
                out += diff(a[k], b[k], f'{path}/{k}')
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f'{path}/{i}')
            if len(out) > 20:
                break
        return out
    return [] if a == b else [path]


def build(root: Path, cmd: list, out: str):
    c = list(cmd)
    c[c.index('--out') + 1] = out
    r = subprocess.run(c, cwd=root, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)[-1200:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--checkout-b', type=Path, required=True)
    ap.add_argument('--only', nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    want = {tuple(s.split(':')) for s in a.only}
    man = json.loads(MAN.read_text())
    rows = []
    for e in man['entries']:
        if (e['region'], e['start'], str(e['horizon_h']), e['variant']) not in want:
            continue
        outA = e['out']
        outB = e['out'].replace('/packets_v35/', '/packets_v35_checkoutB/')
        row = {'entry': f"{e['region']}:{e['start']}:{e['horizon_h']}:{e['variant']}",
               'checkout_a': str(REPO), 'checkout_b': str(a.checkout_b.resolve())}
        for key, root, out in (('A', REPO, outA), ('B', a.checkout_b, outB)):
            if not (root / out / 'HAZARD.json').exists():
                rc, log = build(root, e['cmd'], out)
                row[f'{key}_rc'] = rc
                if rc:
                    row[f'{key}_log'] = log
        pa, pb = REPO / outA, a.checkout_b / outB
        if not (pa / 'HAZARD.json').exists() or not (pb / 'HAZARD.json').exists():
            row['ok'] = False
            rows.append(row); print(json.dumps(row)[:600]); continue
        row['sha256_A'] = {f: sha(pa / f) for f in FILES}
        row['sha256_B'] = {f: sha(pb / f) for f in FILES}
        row['a_two_checkouts_identical'] = row['sha256_A'] == row['sha256_B']
        row['radiation_operator_A'] = json.loads((pa / 'HAZARD.json').read_text())['provenance']['identity']['radiation_operator']
        v34 = REPO / outA.replace('/packets_v35/', '/packets_v34/')
        if (v34 / 'HAZARD.json').exists():
            d = {f: diff(json.loads((v34 / f).read_text()), json.loads((pa / f).read_text()))
                 for f in FILES if f.endswith('.json')}
            allowed = all(p.endswith('/radiation_operator/module') or p.endswith('/radiation_operator/module_path_form')
                          for ps in d.values() for p in ps)
            row['b_vs_v34_json_paths_differing'] = d
            row['b_vs_v34_only_allowed_fields'] = allowed
            row['b_vs_v34_npz_identical'] = sha(v34 / 'constructed_arrays.npz') == sha(pa / 'constructed_arrays.npz')
            row['ok'] = row['a_two_checkouts_identical'] and allowed and row['b_vs_v34_npz_identical']
        else:
            row['b_vs_v34'] = 'no v3.4 packet on disk'
            row['ok'] = row['a_two_checkouts_identical']
        rows.append(row)
        print(json.dumps({k: row[k] for k in ('entry', 'ok', 'a_two_checkouts_identical')}
                         | {'v34': row.get('b_vs_v34_only_allowed_fields', row.get('b_vs_v34'))}))
    a.out.write_text(json.dumps({'rule': 'IDENTITY_PATH_RULE.md', 'manifest_sha256': sha(MAN), 'rows': rows,
                                 'all_ok': bool(rows) and all(r['ok'] for r in rows)}, indent=1))
    print('all_ok', bool(rows) and all(r['ok'] for r in rows), len(rows))


if __name__ == '__main__':
    main()
