#!/usr/bin/env python3
"""Recorded Route-Check API exchanges for the map's "API 응답 보기" viewer.

usage: python3 tools/build_api_log.py      (every region with a booth cache in planner/cache)

Reads the booth cache files the planner wrote while calling the real Route-Check API (planner/cache/<region>/*.json) and
writes site/regions/<id>.api.js, loaded only when the viewer opens:
  WFG_API[id] = { cache: {...INDEX entry}, times: [ { input_time, plans: {dp_…: job}, rc: {rc_…: job}, rows: {origin_id: {...}} } ] }
Nothing is computed or changed: each job is the object the API returned for GET /v1/dispatch-plans/{id} or
GET /v1/route-checks/{id}. Only bulk arrays are folded to a count (route coordinates and their per-point lists, which the
map already draws), and each origin's attempt list inside a dispatch plan (kept in that origin's row).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT.parent / 'cache'
OUT = ROOT / 'site' / 'regions'
BULK = ('times_s', 'node_ids', 'edge_ids', 'waits')


def fold(n, what):
    return f'… {n} {what} (지도에 그린 선 · drawn on the map)'


def trim_rc(j):
    j = json.loads(json.dumps(j))
    r = (j.get('result') or {}).get('route')
    if r:
        r['geometry']['coordinates'] = fold(len(r['geometry']['coordinates']), 'points')
        for k in BULK:
            v = r['properties'].get(k)
            if isinstance(v, list): r['properties'][k] = fold(len(v), 'values')
    return j


def trim_plan(p):
    """Stored once per job; each origin's attempt list lives in its row (rows[...].att) and the viewer puts it back."""
    p = json.loads(json.dumps(p))
    for o in (p.get('result') or {}).get('plans', []):
        if 'attempts' in o: o['attempts'] = len(o['attempts'])
    return p


def main():
    index = json.loads((CACHE / 'INDEX.json').read_text())
    regions = sorted({e['region_id'] for e in index})
    for rid in regions:
        times = []
        for e in sorted((e for e in index if e['region_id'] == rid), key=lambda e: e['input_time']):
            d = json.loads((CACHE / e['path']).read_text())
            rc, plans, rcs, rows = d['route_checks'], {}, {}, {}
            for p in d['plans']:
                for o in (p.get('result') or {}).get('plans', []):
                    oid, best = o['origin_id'], o.get('best') or {}
                    att = o.get('attempts') or []
                    shown = best.get('route_check_job_id') or next((a['route_check_job_id'] for a in att if a.get('route_check_job_id')), None)
                    plans.setdefault(p['job_id'], trim_plan(p))
                    if shown and shown in rc: rcs[shown] = trim_rc(rc[shown])
                    rows[oid] = dict(plan=p['job_id'], rc=shown if shown in rc else None, best=best.get('route_check_job_id'),
                                     att=[[a['destination_id'], a['depart_offset_s'], a['verdict'], a.get('arrival_s'), a.get('compute_s'), a.get('route_check_job_id')] for a in att])
            by = {}
            for x in d['research_checks']:
                if 'job_id' in x and x['job_id'] in rc: by.setdefault(x['origin_id'], []).append(x)
            for oid, lst in by.items():
                lst.sort(key=lambda x: x['depart_offset_s'])
                res = lambda x: rc[x['job_id']].get('result') or {}
                ok = [x for x in lst if res(x).get('verdict') == 'checked_route']
                shown = (ok[-1] if ok else lst[0])['job_id']
                rcs[shown] = trim_rc(rc[shown])
                rows[oid] = dict(plan=None, rc=shown, best=ok[-1]['job_id'] if ok else None,
                                 att=[[x['destination_id'], x['depart_offset_s'], res(x).get('verdict', 'unresolved'), res(x).get('arrival_s'), res(x).get('compute_s'), x['job_id']] for x in lst])
            times.append(dict(input_time=d['input_time'], scenario_set_id=d['scenario_set_id'], base=d['api'].get('base'), health=d['api'].get('health'),
                              plans=plans, rc=rcs, rows=rows))
        meta = next(e for e in index if e['region_id'] == rid)
        body = dict(cache=dict(api_version=meta.get('api_version'), mode=meta.get('api_mode'), host=meta.get('host'), created_at=meta.get('created_at')), times=times)
        text = f'(window.WFG_API=window.WFG_API||{{}})[{json.dumps(rid)}]=' + json.dumps(body, ensure_ascii=False, separators=(',', ':')) + ';\n'
        (OUT / f'{rid}.api.js').write_text(text)
        print(f'{rid}: {sum(len(t["rows"]) for t in times)} origins over {len(times)} input times, {len(text.encode()) / 1e6:.2f} MB')


if __name__ == '__main__':
    main()
