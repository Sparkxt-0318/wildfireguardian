"""G6a comparison (G6A_RUN.md "Comparisons" and "Pass"; G6_RULE.md). Reads RUN_DIR/{P1,P2,V,R}/ROWS.jsonl.
  python -B g6_compare.py RUN_DIR --certs TIMEOUT_NO_ROUTE_CERTS_1h.json --v2-kit KIT [--exceptions-only] [--json OUT]
                         [--rerun-list R_JOBS.json]
--exceptions-only: after P1 and P2, write the FL2-type exception list (P1 != P2) and stop (committed before V runs).
Outcome key: (verdict, arrival_s if checked_route). Route triples (edge_ids, times_s, waits) and raw_status are
compared and reported, never a failure on their own.
"""
import argparse, json
from collections import Counter
from pathlib import Path


def rows(p):
    return {(r['cache'], r['job_id']): r for r in map(json.loads, filter(str.strip, p.read_text().splitlines()))} if p.exists() else {}


def key(r):
    o = r['outcome']
    return (o.get('verdict'), o.get('arrival_s') if o.get('verdict') == 'checked_route' else None)


def vs_record(r, cert):
    """None if allowed by G6_RULE's table, else a short reason. cert: the router-field row for TIMEOUT jobs."""
    rec, o = r['recorded'], r['outcome']
    if rec.get('raw_status') == 'AT_ISSUE_FAILURE':
        return None if o.get('raw_status') == 'AT_ISSUE_FAILURE' else 'AT_ISSUE_EXPECTED'
    if rec.get('verdict') == 'checked_route':
        return None if o.get('verdict') == 'checked_route' and o.get('arrival_s') == rec.get('arrival_s') else 'ROUTE_ARRIVAL_DIFFERS'
    if rec.get('verdict') == 'model_no_route':
        return None if o.get('raw_status') == 'FULL_MODEL_REFUSAL_PROVEN' else 'REFUSAL_EXPECTED'
    # timeout: anything except a contradiction of the router-only field
    if cert is None:
        return 'NO_FIELD_ROW'
    if cert['status'] == 'NO_ROUTE_CERT' and o.get('verdict') == 'checked_route':
        return 'CONTRADICTION_ROUTE_ON_CERTIFIED_NO_ROUTE'
    if cert['status'].startswith('FEASIBLE') and o.get('raw_status') == 'FULL_MODEL_REFUSAL_PROVEN':
        return 'CONTRADICTION_REFUSAL_ON_FEASIBLE'
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path); ap.add_argument('--certs', type=Path, required=True)
    ap.add_argument('--v2-kit', type=Path); ap.add_argument('--exceptions-only', action='store_true')
    ap.add_argument('--json', type=Path); ap.add_argument('--rerun-list', type=Path)
    a = ap.parse_args()
    P1, P2, V, R = (rows(a.run / ph / 'ROWS.jsonl') for ph in ('P1', 'P2', 'V', 'R'))
    sample = json.loads((Path(__file__).resolve().parents[1] / 'G6A_SAMPLE.json').read_text())['jobs']
    ids = [(j['cache'], j['job_id']) for j in sample]
    missing = {ph: [i for i in ids if i not in d] for ph, d in (('P1', P1), ('P2', P2))}
    assert not missing['P1'] and not missing['P2'], {k: len(v) for k, v in missing.items()}
    fl2 = [i for i in ids if key(P1[i]) != key(P2[i])]
    out = {'fl2_type_exceptions': [{'cache': c, 'job_id': j, 'P1': key(P1[(c, j)]), 'P2': key(P2[(c, j)])} for c, j in fl2],
           'parent_harness_errors': [list(i) for i in ids if 'HARNESS_ERROR' in (key(P1[i])[0], key(P2[i])[0])]}
    if a.exceptions_only:
        print(json.dumps({'fl2_type_exceptions': len(fl2), 'parent_harness_errors': len(out['parent_harness_errors'])}))
        for x in out['fl2_type_exceptions']:
            print(json.dumps(x))
        if a.json:
            a.json.write_text(json.dumps(out, indent=1, default=str) + '\n')
        return
    certs = {}
    for c in json.loads(a.certs.read_text())['rows']:
        certs[(c['cache'].split('planner/cache/')[-1], c['job'])] = c
    assert len(certs) == 297, len(certs)
    want = json.loads((a.v2_kit / 'KIT_IDENTITY.json').read_text()) if a.v2_kit else None
    assert not [i for i in ids if i not in V], 'phase V incomplete'
    fails, rerun, ties, rawdiff, contra, idbad, inbad, errors = [], [], [], [], [], [], [], []
    rec_parent, rec_v2 = Counter(), Counter(); rec_parent_list = []
    for i in ids:
        p1, p2, v = P1[i], P2[i], R.get(i, V[i])
        pset = {key(p1), key(p2)}
        if 'HARNESS_ERROR' in (key(v)[0], key(p1)[0], key(p2)[0]):
            errors.append(list(i)); continue
        if key(v) not in pset:
            capped = v['outcome'].get('wall_cap') or p1['outcome'].get('wall_cap') or p2['outcome'].get('wall_cap')
            entry = {'cache': i[0], 'job_id': i[1], 'stratum': v.get('stratum'), 'V2': key(v), 'PARENT': sorted(pset, key=str),
                     'wall_cap_involved': bool(capped), 'after_rerun': i in R}
            (rerun if capped and i not in R else fails).append(entry)
        elif key(v)[0] == 'checked_route' and (v['outcome'].get('route') != p1['outcome'].get('route')):
            ties.append({'cache': i[0], 'job_id': i[1], 'arrival_s': key(v)[1]})
        if v['outcome'].get('raw_status') != p1['outcome'].get('raw_status') and key(v) in pset:
            rawdiff.append({'cache': i[0], 'job_id': i[1], 'V2': v['outcome'].get('raw_status'), 'PARENT': p1['outcome'].get('raw_status')})
        cert = certs.get(i) if v.get('stratum') == 'TIMEOUT' else None
        rv, rp = vs_record(v, cert), vs_record(p1, cert)
        rec_v2[rv or 'OK'] += 1; rec_parent[rp or 'OK'] += 1
        if rv and rv.startswith('CONTRADICTION'):
            contra.append({'cache': i[0], 'job_id': i[1], 'reason': rv, 'V2': key(v), 'PARENT_same': rp == rv})
        if rp:
            rec_parent_list.append({'cache': i[0], 'job_id': i[1], 'reason': rp, 'PARENT': key(p1), 'RECORD': p1['recorded']})
        if want and (v.get('kit_identity') or {}).get('overlay_sha256') != want.get('overlay_sha256'):
            idbad.append(list(i))
        if v.get('request_sha256') != p1.get('request_sha256') or v.get('input_check', {}).get('hazard_sha256') != p1.get('input_check', {}).get('hazard_sha256'):
            inbad.append(list(i))
    out.update(g6_failures=fails, rerun_needed=rerun, equal_arrival_ties=ties, raw_status_differences=rawdiff,
               v2_timeout_contradictions=contra, kit_identity_mismatch=idbad, input_or_request_mismatch=inbad,
               harness_errors=errors, parent_vs_record=dict(rec_parent), v2_vs_record=dict(rec_v2),
               parent_vs_record_list=rec_parent_list)
    out['verdict_counts'] = {'V2': dict(Counter(key(R.get(i, V[i]))[0] for i in ids)), 'PARENT_P1': dict(Counter(key(P1[i])[0] for i in ids))}
    out['PASS'] = (not fails and not rerun and not contra and not idbad and not inbad and not errors)
    if a.rerun_list and rerun:
        a.rerun_list.write_text(json.dumps({'jobs': [{'cache': x['cache'], 'job_id': x['job_id'], 'stratum': x['stratum']} for x in rerun]}, indent=1) + '\n')
    summary = {k: (len(v) if isinstance(v, list) else v) for k, v in out.items() if k != 'parent_vs_record_list'}
    print(json.dumps(summary, default=str))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
