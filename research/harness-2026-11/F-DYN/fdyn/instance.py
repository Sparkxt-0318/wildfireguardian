"""F-DYN workload instance: origins (the 174 planner places at their road entry nodes) and their 3 candidate
destinations (the recorded planner dispatch plans: nearest OSM schools/halls/shelter with distinct entry nodes), with a
fixed departure grid over the multi-hour horizon. Reads the recorded planner cache via research/solve2027-impact
(planner rules); no route checks.

    python3 research/harness-2026-11/F-DYN/fdyn/instance.py --out INSTANCE.json [--step-min 30] [--horizons 5 8]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'research' / 'solve2027-impact'))

from wfg_impact import analysis  # noqa: E402

SCHEMA = 'wfg.fdyn.instance/1'
DWELL_S = 120


def build(horizons_h=(5, 8), step_min=30):
    out = analysis.run(with_graphs=False)
    starts = {}
    for r in out['records']:
        if r['origin_type'] not in ('village', 'care_facility') or not r.get('dest_nodes'):
            continue
        key = (r['region'], r['input_time'])
        o = {'origin_id': r['origin_id'], 'name': r['name'], 'name_en': r['name_en'], 'origin_type': r['origin_type'],
             'entry_node': r['entry_node'], 'entry_distance_m': r.get('entry_distance_m'),
             'destinations': [{'destination_id': d, 'node': n, 'dwell_s': w}
                              for d, n, w in zip(r['dest_ids'], r['dest_nodes'], r['dest_dwell_s'])]}
        starts.setdefault(key, []).append(o)
    instances = []
    for (region, t), origins in sorted(starts.items()):
        tag = t.replace('-', '').replace(':', '')
        for h in horizons_h:
            H = int(h * 3600)
            instances.append({
                'region': region, 'start_utc': t, 'start_tag': tag, 'horizon_s': H,
                'packet': f'packets/{region}/{tag}_h{int(h)}',
                'depart_offsets_s': list(range(0, H, step_min * 60)),
                'destination_window_s': [0, H], 'dwell_s': DWELL_S,
                'limits': {'peak_kw_m2': 10, 'dose_kj_m2': 100},
                'origins': sorted(origins, key=lambda o: o['origin_id'])})
    return {'schema': SCHEMA,
            'label': 'SCENARIO workload from a retrospective arrival-time reconstruction; not what happened',
            'origins_source': 'planner/cache (recorded 2025 dispatch plans) and planner places.geojson entry nodes',
            'instances': instances}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--step-min', type=int, default=30)
    ap.add_argument('--horizons', type=float, nargs='+', default=[5, 8])
    a = ap.parse_args()
    doc = build(tuple(a.horizons), a.step_min)
    a.out.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    n = sum(len(i['origins']) for i in doc['instances'])
    print(f"{len(doc['instances'])} instances, {n} origin-instances -> {a.out}")


if __name__ == '__main__':
    main()
