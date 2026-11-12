"""DESIGN.md amendment A1 (post hoc, proposed): evaluate the cross-environment comparison of the frozen writer's
rebuilds (A, from regress.py work dirs) against the stored frozen packets under BOTH rules, side by side. No rebuild.

  existing (of record): ids, breakpoints, flame, support exact; flux relative <= 1e-9
  A1 (proposed):        same, but a flux entry passes if relative <= 1e-9 OR absolute <= 1e-12 kW/m2

Writer identity of every compared instance is recorded (packet_writer_sha256, support_writer if any).

    python3 research/harness-2026-11/F-9.3/support_mask/amended_rule.py --run LABEL=WORKDIR [--run LABEL=WORKDIR ...] \
        --out AMENDED_RULE_RESULTS.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
STORED = REPO / 'data' / 'routing' / 'latest_inputs_try02' / 'packets'
REL, ABS = 1e-9, 1e-12


def writer(hz):
    i = hz['provenance']['identity']
    return {'packet_writer_sha256': i['packet_writer_sha256'], 'support_writer': i.get('support_writer')}


def compare(built: Path, stored: Path) -> dict:
    h1 = json.loads((built / 'HAZARD.json').read_text()); h0 = json.loads((stored / 'HAZARD.json').read_text())
    out = {'writer_built': writer(h1), 'writer_stored': writer(h0)}
    exact = [m['id'] for m in h1['members']] == [m['id'] for m in h0['members']]
    n = fail_rel = fail_a1 = 0
    worst_rel = worst_abs = 0.0
    for m1, m0 in zip(h1['members'], h0['members']):
        exact &= all(m1[k] == m0[k] for k in ('breakpoints', 'flame', 'support'))
        f1, f0 = np.asarray(m1['flux'], float), np.asarray(m0['flux'], float)
        if f1.shape != f0.shape:
            exact = False
            continue
        d = np.abs(f1 - f0)
        rel = np.where(d == 0, 0.0, d / np.maximum(np.abs(f0), 1e-300))
        n += d.size
        fail_rel += int((rel > REL).sum())
        fail_a1 += int(((rel > REL) & (d > ABS)).sum())
        worst_rel = max(worst_rel, float(rel.max()) if rel.size else 0.0)
        worst_abs = max(worst_abs, float(d.max()) if d.size else 0.0)
    out.update(ids_breakpoints_flame_support_exact=bool(exact), flux_entries=n, flux_max_relative=worst_rel,
               flux_max_absolute_kW_m2=worst_abs, entries_failing_existing=fail_rel, entries_failing_A1=fail_a1,
               existing_rule='PASS' if exact and fail_rel == 0 else 'FAIL',
               A1_rule='PASS' if exact and fail_a1 == 0 else 'FAIL')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='append', required=True, help='LABEL=regress.py work dir')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    runs = {}
    for spec in a.run:
        label, work = spec.split('=', 1)
        rows = []
        for stored in sorted(STORED.glob('*/*')):
            built = Path(work) / stored.parent.name / stored.name / 'A'
            if not (built / 'HAZARD.json').exists():
                rows.append({'packet': f'{stored.parent.name}/{stored.name}', 'status': 'NO_REBUILD'})
                continue
            rows.append({'packet': f'{stored.parent.name}/{stored.name}', **compare(built, stored)})
        runs[label] = {'rows': rows,
                       'existing_rule_pass': sum(r.get('existing_rule') == 'PASS' for r in rows),
                       'A1_rule_pass': sum(r.get('A1_rule') == 'PASS' for r in rows), 'packets': len(rows)}
        print(label, {k: v for k, v in runs[label].items() if k != 'rows'})
        for r in rows:
            print(' ', r['packet'], r.get('existing_rule'), r.get('A1_rule'), '%.2e' % r.get('flux_max_relative', 0),
                  '%.2e' % r.get('flux_max_absolute_kW_m2', 0), r.get('entries_failing_existing'), r.get('entries_failing_A1'))
    a.out.write_text(json.dumps({'schema': 'wfg.f93.support-writer.amended-rule/1',
                                 'status': 'A1 is POST HOC and PROPOSED; the existing rule (relative 1e-9) is the rule of record',
                                 'existing_rule': {'flux_relative_max': REL},
                                 'A1_rule': {'flux_relative_max': REL, 'or_flux_absolute_max_kW_m2': ABS},
                                 'runs': runs}, indent=1))


if __name__ == '__main__':
    main()
