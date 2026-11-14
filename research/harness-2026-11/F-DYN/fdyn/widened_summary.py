"""WIDENED_GRAPH_RULE.md: summary of the router-only runs for one region (classes, P4/P4-open/P6, coverage, effects).

Per (place, start, horizon, variant), CERT, union over the place's destinations, any departure in [0, H]:
  class (§2.3, padding arms under waiting (b), the headline):
    closed route                     -> "route found by the router on the widened graph, to the listed destinations;
                                         not independently checked"
    closed none, open route          -> "undetermined: depends on fire outside the export grid"
    closed none, open none           -> "no route found by the router on the widened graph to the listed destinations;
                                         not independently checked"
  widening effect (§8, 78a): widened (a) closed vs G1;  waiting effect (§3): (b) vs (a), padding closed.
  "leaves the old window": every in-window widened edge is a G1 edge (step-2 equality; WIDENED_INPUTS 0 differing), so a
  widened route at a departure where G1 has none must use an edge with an endpoint outside the window.
Asserted (any violation -> FAIL): P4, P4-open, P6 (both waiting arms). Coverage floor (§8(iii)3) on the control set.

    python3 fdyn/widened_summary.py --runs RUNS_DIR --region R --out results/WIDENED_RESULTS_<R>.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

CLS = {'closed': 'route found by the router on the widened graph, to the listed destinations; not independently checked',
       'undet': 'undetermined: depends on fire outside the export grid',
       'none': 'no route found by the router on the widened graph to the listed destinations; not independently checked'}


def place_union(sets, entry, grid):
    """§4 / row 82 (3): a route counts when the feasible set holds at least one 30-min grid departure."""
    ivs = [p for k, v in sets.items() if k.startswith('cert|') and k.split('|')[1] == entry for p in v]
    return any(a_ <= t <= b for t in grid for a_, b in ivs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=Path, required=True)
    ap.add_argument('--region', required=True)
    ap.add_argument('--instance', type=Path, default=Path(__file__).resolve().parents[1] / '_data' / 'INSTANCE.json')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    inst = json.loads(a.instance.read_text())['instances']
    grids = {(i['start_tag'], i['horizon_s']): i['depart_offsets_s'] for i in inst if i['region'] == a.region}
    entry_of = {(i['start_tag'], o['origin_id']): o['entry_node'] for i in inst if i['region'] == a.region for o in i['origins']}
    out = {'rule': 'WIDENED_GRAPH_RULE.md', 'region': a.region,
           'label': 'roads as of 2025-01-01 (before the March 2025 fires); router-only, not independently checked; '
                    'no fire data outside the export grid; not shown safe',
           'runs': [], 'fail': []}
    classes, widening, waiting, leaves = Counter(), Counter(), Counter(), Counter()
    per_place = []
    for kind in ('candidates', 'control'):
        for f in sorted((a.runs / kind / a.region).glob('*.json')):
            d = json.loads(f.read_text())
            S = d['sets']
            row = {'file': f.name, 'kind': kind, 'start': d['start'], 'horizon_h': d['horizon_h'], 'places': d['places'],
                   'P4': {k: d['P4'][k] for k in ('triples', 'nonempty', 'departure_seconds', 'violations')},
                   'P4_open_violations': d['P4_open']['violations'], 'P6': d['P6'], 'coverage': d.get('coverage'),
                   'peak_rss_mib': max(d['peak_rss_mib'].values())}
            v = d['P4']['violations'] + d['P4_open']['violations'] + sum(
                x['closed_subset_open_violations'] + x['closed_witness_touching_padding'] for x in d['P6'].values())
            if v:
                out['fail'].append({'file': f.name, 'violations': v})
            out['runs'].append(row)
            if kind != 'candidates':
                continue
            variant = f.stem.split('_', 2)[2]
            grid = grids[(d['start'], d['horizon_h'] * 3600)]
            entries = sorted({k.split('|')[1] for k in S['a_closed'] if k.startswith('cert|')})
            for e in entries:
                g1 = place_union(S['g1'], e, grid)
                ac, ao = place_union(S['a_closed'], e, grid), place_union(S['a_open'], e, grid)
                bc, bo = place_union(S['b_closed'], e, grid), place_union(S['b_open'], e, grid)
                c = 'closed' if bc else ('undet' if bo else 'none')
                classes[(d['start'], d['horizon_h'], variant, c)] += 1
                widening[('G1 route' if g1 else 'G1 none', 'widened(a) closed route' if ac else 'widened(a) closed none')] += 1
                waiting[('(a) route' if ac else '(a) none', '(b) route' if bc else '(b) none')] += 1
                if ac and not g1:
                    leaves['widened (a) closed route where G1 has none: leaves the old window'] += 1
                per_place.append({'start': d['start'], 'horizon_h': d['horizon_h'], 'variant': variant, 'entry_node': e,
                                  'g1': g1, 'a_closed': ac, 'a_open': ao, 'b_closed': bc, 'b_open': bo, 'class': CLS[c]})
    ctrl = [r for r in out['runs'] if r['kind'] == 'control']
    if ctrl:
        c = ctrl[0]
        cov = c['coverage'] or {}
        meets = (cov.get('ratio') or 0) >= 0.5 and (cov.get('g1p_nonempty_triples') or 0) >= 50
        out['coverage_floor'] = {'ratio': cov.get('ratio'), 'nonempty_triples': cov.get('g1p_nonempty_triples'),
                                 'meets_fixed_minimum': meets,
                                 'P4_report': 'PASS' if meets and not out['fail'] else
                                 ('held, but below the fixed coverage minimum: tests little' if not out['fail'] else 'FAIL')}
    out['classes_headline_waiting_b'] = [{'start': k[0], 'horizon_h': k[1], 'variant': k[2], 'class': CLS[k[3]], 'n': n}
                                         for k, n in sorted(classes.items())]
    out['widening_effect_vs_G1'] = {f'{k[0]} -> {k[1]}': n for k, n in sorted(widening.items())}
    out['waiting_effect_a_vs_b_closed'] = {f'{k[0]} -> {k[1]}': n for k, n in sorted(waiting.items())}
    out['leaves_old_window'] = dict(leaves)
    out['per_place'] = per_place
    out['all_asserted_pass'] = not out['fail']
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ('region', 'all_asserted_pass', 'fail', 'coverage_floor', 'widening_effect_vs_G1',
                                          'waiting_effect_a_vs_b_closed', 'leaves_old_window') if k in out}, indent=1))


if __name__ == '__main__':
    main()
