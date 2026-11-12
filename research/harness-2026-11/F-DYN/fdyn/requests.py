"""Routing requests for built F-DYN packets: a mechanical mapping of INSTANCE.json (wfg.fdyn.instance/1) onto the
writer's request template (integration/src/wfg_latest/packets.py `template`). No rule and no tuning: every field is
copied or fixed as stated below.

One request per (manifest entry, origin, departure offset):
  position        {"node": origin.entry_node}             incoming_edge  None
  departure       offset (int s, from INSTANCE depart_offsets_s for the region and horizon)
  horizon         horizon_s (int s)
  destinations    [{"node": d.node, "dwell": d.dwell_s, "open_intervals": [destination_window_s]}]
  incurred        {member_id: 0 for every packet member}
  budgets         {"peak": limits.peak_kw_m2, "dose": {member_id: limits.dose_kj_m2}}   (template units: 10 / 100)
  hazard_version  HAZARD.version          as_of  HAZARD.time_origin
  objective "earliest_arrival", exposure_scope "including_dwell", solver "baseline"  (writer template)
  limits          api/config.py REQUEST_LIMITS (wall_s 30, max_labels 1e6, max_expansions 1e6, frontier_width 16384);
                  the writer template's {"wall_s": 30} alone fails router validation (max_labels required)
Member ids are read from the built packet's HAZARD.json, so requests are only written for packets that exist.

    python3 research/harness-2026-11/F-DYN/fdyn/requests.py --manifest research/harness-2026-11/F-DYN/MANIFEST_v3_3.json \
        --instance research/harness-2026-11/F-DYN/_data/INSTANCE.json --out-dir OUT [--only REGION:START:H:VARIANT ...]
Writes OUT/<region>/<start>_h<H>_<variant>/<origin_id>__d<offset>.json and OUT/REQUESTS_MANIFEST.json (sha256 per file,
keyed by region, start, horizon_h, variant, origin_id, departure_s).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA = 'wfg.fdyn.requests/1'
REQUEST_LIMITS = {'wall_s': 30, 'max_labels': 1000000, 'max_expansions': 1000000, 'frontier_width': 16384}
try:                                    # keep in lockstep with the API's own request limits when importable
    import sys as _s
    _s.path.insert(0, str(REPO))
    from api.config import REQUEST_LIMITS as _API_LIMITS
    if dict(_API_LIMITS) != REQUEST_LIMITS:
        raise SystemExit(f'REQUEST_LIMITS_DIFFER_FROM_API {_API_LIMITS}')
except ImportError:
    pass
FIXED = {'incoming_edge': None, 'objective': 'earliest_arrival', 'exposure_scope': 'including_dwell',
         'limits': REQUEST_LIMITS, 'solver': 'baseline'}


def safe(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9._-]', '_', s)


def requests_for(entry: dict, inst: dict, hazard: dict, graph_nodes: set) -> list[tuple[dict, dict]]:
    ids = [m['id'] for m in hazard['members']]
    H = int(entry['horizon_h'] * 3600)
    if int(inst['horizon_s']) != H:
        raise SystemExit(f"INSTANCE_HORIZON_MISMATCH {inst['horizon_s']} != {H}")
    lim = inst['limits']
    out = []
    for o in inst['origins']:
        if o['entry_node'] not in graph_nodes:
            raise SystemExit(f"ORIGIN_NODE_NOT_IN_GRAPH {o['entry_node']}")
        dests = [{'node': d['node'], 'dwell': int(d['dwell_s']), 'open_intervals': [list(inst['destination_window_s'])]}
                 for d in o['destinations']]
        for d in dests:
            if d['node'] not in graph_nodes:
                raise SystemExit(f"DESTINATION_NODE_NOT_IN_GRAPH {d['node']}")
        for dep in inst['depart_offsets_s']:
            req = {'position': {'node': o['entry_node']}, 'departure': int(dep), 'horizon': H, 'destinations': dests,
                   'incurred': {i: 0 for i in ids}, 'hazard_version': hazard['version'], 'as_of': hazard['time_origin'],
                   'budgets': {'peak': lim['peak_kw_m2'], 'dose': {i: lim['dose_kj_m2'] for i in ids}}, **FIXED}
            key = {'region': entry['region'], 'start': entry['start'], 'horizon_h': entry['horizon_h'],
                   'variant': entry['variant'], 'soundness': entry['soundness'], 'origin_id': o['origin_id'],
                   'departure_s': int(dep)}
            out.append((key, req))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--instance', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--only', nargs='*', default=None, help='REGION:START:H:VARIANT entries to restrict to')
    a = ap.parse_args()
    man = json.loads(a.manifest.read_text())
    insts = {(i['region'], int(i['horizon_s'])): i for i in json.loads(a.instance.read_text())['instances']}
    only = None if a.only is None else {tuple(s.split(':')) for s in a.only}
    rows, skipped = [], []
    graphs = {}
    for e in man['entries']:
        if only is not None and (e['region'], e['start'], str(int(e['horizon_h'])), e['variant']) not in only:
            continue
        pdir = REPO / e['out']
        if not (pdir / 'HAZARD.json').exists():
            skipped.append(e['out'])
            continue
        hazard = json.loads((pdir / 'HAZARD.json').read_text())
        gpath = e['cmd'][e['cmd'].index('--graph') + 1]
        if gpath not in graphs:
            graphs[gpath] = {n['id'] for n in json.loads((REPO / gpath).read_text())['nodes']}
        inst = insts[(e['region'], int(e['horizon_h'] * 3600))]
        sub = a.out_dir / e['region'] / Path(e['out']).name
        sub.mkdir(parents=True, exist_ok=True)
        for key, req in requests_for(e, inst, hazard, graphs[gpath]):
            p = sub / f"{safe(key['origin_id'])}__d{key['departure_s']}.json"
            body = json.dumps(req, indent=1, sort_keys=True).encode()
            p.write_bytes(body)
            rows.append({**key, 'path': str(p.relative_to(a.out_dir)), 'sha256': hashlib.sha256(body).hexdigest(),
                         'packet_hazard_sha256': hashlib.sha256((pdir / 'HAZARD.json').read_bytes()).hexdigest()})
    (a.out_dir / 'REQUESTS_MANIFEST.json').write_text(json.dumps(
        {'schema': SCHEMA, 'manifest': str(a.manifest), 'manifest_sha256': hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
         'instance_sha256': hashlib.sha256(a.instance.read_bytes()).hexdigest(), 'requests': rows,
         'skipped_entries_without_packet': skipped}, indent=1))
    print(json.dumps({'requests': len(rows), 'entries_skipped_no_packet': len(skipped)}))


if __name__ == '__main__':
    main()
