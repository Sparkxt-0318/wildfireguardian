"""G6b classification of one cache (G6B_RUN.md "Classification"; G6A_RULING.md (1)/(2)).
  WFG_WFT=/path/to/F-3.2-checkout python -B g6b_classify.py CACHE_DIR --cache CACHE_REL --frozen FROZEN_KIT --v2-kit V2_KIT
Reads CACHE_DIR/{P1,P2,V,R}/ROWS.jsonl. Writes CACHE_DIR/CLASSIFY.json with one class per job:
  unchanged | allowed_optimum_confirmed | allowed_optimality_not_verified | failure:<reason> | stop:<reason>
plus listed items (ties, raw_status differences, pre-existing PARENT != RECORD). Exit code 3 if any job is failure:* or
stop:* (the driver's stop rule), else 0.
Candidates for an allowed difference get (2a) tools/g2_recheck.py (both frozen checkers, fresh interpreters) and (2c)
g2b @ deeb7c2 on their V2 run folders.
"""
import argparse, json, os, subprocess, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2DIR = HERE.parent
TIME_CAPPED = {'LATE_RESULT', 'DEADLINE_STOP', 'SEARCH_TIMEOUT'}   # closed list (G6A_RULING (1)); never extended after a run


def rows(p):
    return {(r['cache'], r['job_id']): r for r in map(json.loads, filter(str.strip, p.read_text().splitlines()))} if p.exists() else {}


def key(r):
    o = r['outcome']
    return (o.get('verdict'), o.get('arrival_s') if o.get('verdict') == 'checked_route' else None)


def time_capped(r):
    o = r['outcome']
    return o.get('verdict') == 'unresolved' and o.get('reason_code') == 'TIMEOUT' and o.get('raw_reason') in TIME_CAPPED


def vs_record(r, cert):
    rec, o = r['recorded'], r['outcome']
    if rec.get('raw_status') == 'AT_ISSUE_FAILURE':
        return None if o.get('raw_status') == 'AT_ISSUE_FAILURE' else 'AT_ISSUE_EXPECTED'
    if rec.get('verdict') == 'checked_route':
        return None if o.get('verdict') == 'checked_route' and o.get('arrival_s') == rec.get('arrival_s') else 'ROUTE_ARRIVAL_DIFFERS'
    if rec.get('verdict') == 'model_no_route':
        return None if o.get('raw_status') == 'FULL_MODEL_REFUSAL_PROVEN' else 'REFUSAL_EXPECTED'
    if cert is None:
        return 'NO_FIELD_ROW'
    if cert['status'] == 'NO_ROUTE_CERT' and o.get('verdict') == 'checked_route':
        return 'CONTRADICTION_ROUTE_ON_CERTIFIED_NO_ROUTE'
    if cert['status'].startswith('FEASIBLE') and o.get('raw_status') == 'FULL_MODEL_REFUSAL_PROVEN':
        return 'CONTRADICTION_REFUSAL_ON_FEASIBLE'
    return None


def run_dir(cache_dir, phase, r):
    return cache_dir / phase / 'jobs' / ('%s__%s' % (Path(r['cache']).with_suffix('').as_posix().replace('/', '__'), r['job_id'])) / 'run'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cache_dir', type=Path); ap.add_argument('--cache', required=True)
    ap.add_argument('--frozen', type=Path, required=True); ap.add_argument('--v2-kit', type=Path, required=True)
    ap.add_argument('--jobs', type=Path, default=V2DIR / 'G6B_JOBS.json')   # validation only (G6a known answer)
    a = ap.parse_args()
    D = a.cache_dir
    P1, P2, V, R = (rows(D / ph / 'ROWS.jsonl') for ph in ('P1', 'P2', 'V', 'R'))
    ids = [(j['cache'], j['job_id']) for j in json.loads(a.jobs.read_text())['jobs'] if j['cache'] == a.cache]
    for nm, d in (('P1', P1), ('P2', P2), ('V', V)):
        miss = [i for i in ids if i not in d]
        assert not miss, (nm, len(miss))
    certs = {(c['cache'].split('planner/cache/')[-1], c['job']): c
             for c in json.loads((V2DIR / 'results/g6a/TIMEOUT_NO_ROUTE_CERTS_1h.c0e34d4.json').read_text())['rows']}
    cx = {(c['cache'].split('planner/cache/')[-1], c['job']): c
          for c in json.loads((V2DIR / 'results/g6a/JOBS_1h_crossref.5389803e.json').read_text())['rows']}
    want = json.loads((a.v2_kit / 'KIT_IDENTITY.json').read_text())['overlay_sha256']
    out, listed, cand = {}, {'ties': [], 'raw_status_differences': [], 'pre_existing_parent_vs_record': []}, []
    for i in ids:
        p1, p2, v = P1[i], P2[i], R.get(i, V[i])
        if 'HARNESS_ERROR' in (key(p1)[0], key(p2)[0], key(v)[0]) or 'INPUT_MISMATCH' in (key(p1)[0], key(p2)[0], key(v)[0]):
            out[i] = 'stop:harness_or_input_error'; continue
        if (v.get('kit_identity') or {}).get('overlay_sha256') != want:
            out[i] = 'stop:kit_identity_mismatch'; continue
        if v.get('request_sha256') != p1.get('request_sha256') or v.get('request_sha256') != p2.get('request_sha256'):
            out[i] = 'stop:request_mismatch'; continue
        cert = certs.get(i) if v['stratum'] == 'TIMEOUT' else None
        rv, rp = vs_record(v, cert), vs_record(p1, cert)
        if rv and rv.startswith('CONTRADICTION'):
            out[i] = 'failure:v2_timeout_contradiction'; continue
        pset = {key(p1), key(p2)}
        if key(v) in pset:
            if rv and not rp:
                out[i] = 'failure:v2_disagrees_with_record_where_parent_agrees'; continue
            out[i] = 'unchanged'
            if rp:
                listed['pre_existing_parent_vs_record'].append({'job': list(i), 'reason': rp})
            if key(v)[0] == 'checked_route' and all(v['outcome'].get('route') != p['outcome'].get('route') for p in (p1, p2) if key(p) == key(v)):
                listed['ties'].append(list(i))
            praw = {p1['outcome'].get('raw_status'), p2['outcome'].get('raw_status')}
            if v['outcome'].get('raw_status') not in praw:
                listed['raw_status_differences'].append({'job': list(i), 'V2': v['outcome'].get('raw_status'), 'PARENT': sorted(praw, key=str)})
            continue
        # a difference: allowed only under every clause of G6A_RULING (1)
        if not (time_capped(p1) and time_capped(p2)):
            out[i] = 'failure:parent_not_time_capped_in_both_runs (%s/%s -> %s)' % (key(p1)[0], key(p2)[0], key(v)[0]); continue
        if key(v)[0] != 'checked_route':
            out[i] = 'failure:v2_not_a_checked_route (%s)' % key(v)[0]; continue
        o = v['outcome']
        if not (o.get('complete_wall_s') is not None and o['complete_wall_s'] <= 81.0):
            out[i] = 'failure:v2_outside_time_limit'; continue
        c = (cx.get(i) or {}).get('router') or {}
        if not c.get('feasible'):
            out[i] = 'failure:route_on_router_infeasible'; continue
        if rv:
            out[i] = 'failure:v2_vs_record_%s' % rv; continue
        cand.append((i, run_dir(D, 'R' if i in R else 'V', v), o.get('arrival_s'), c.get('arrival')))
    # (2a) both frozen checkers and (2c) g2b on every candidate
    checks = {}
    if cand:
        dirs = [str(d) for _, d, _, _ in cand]
        g2 = D / 'G2_RECHECK_CANDIDATES.jsonl'
        subprocess.run([sys.executable, '-B', str(HERE / 'g2_recheck.py'), '--frozen', str(a.frozen), '--out', str(g2)] + dirs,
                       check=True, capture_output=True, text=True)
        g2r = {r['run']: r for r in map(json.loads, g2.read_text().splitlines())}
        wft = Path(os.environ['WFG_WFT'])
        cc = next(wft.glob('research/harness-2026-11/F-3.2/**/wfgc_check'))
        g2b_out = D / 'G2B_CANDIDATES.json'
        env = dict(os.environ, PYTHONPATH='experimental/sipp-routing/src:experimental/scenario-members/src:experimental/synthetic-truth/src')
        subprocess.run(['python', '-B', 'research/harness-2026-11/F-3.2/xcheck/g2b.py', '--kit-root', str(a.v2_kit), '--runs'] + dirs +
                       ['--c-checker', str(cc), '--out', str(g2b_out)], cwd=str(wft), env=env, check=False, capture_output=True, text=True)
        g2b = [r for r in json.loads(g2b_out.read_text()) if isinstance(r, dict) and 'verdict' in r]
        assert len(g2b) == len(cand), (len(g2b), len(cand))
        for (i, d, arr, rarr), gb in zip(cand, g2b):
            assert str(gb.get('arrival')) == str(arr), (i, gb.get('arrival'), arr)
            g = g2r.get(str(Path(d).resolve()))   # g2_recheck records the resolved path (validation caught the miss)
            assert g is not None, ('no g2_recheck row for', str(d))
            checks[i] = {'g2a_pass': bool(g.get('pass')), 'g2b': gb['verdict'], 'g2b_note': gb.get('note'), 'arrival': arr, 'router_arrival': rarr}
            if not g.get('pass'):
                out[i] = 'failure:frozen_checker_rejects_route'
            elif arr == rarr:
                out[i] = 'allowed_optimum_confirmed'
            elif arr < rarr:
                out[i] = 'failure:arrival_earlier_than_router_optimum'
            else:
                out[i] = 'stop:witness_needed (arrival %s > router optimum %s)' % (arr, rarr)
    res = {'cache': a.cache, 'jobs': len(ids), 'classes': dict(Counter(v.split(' (')[0] for v in out.values())),
           'by_stratum': {s: dict(Counter(out[i].split(' (')[0] for i in ids if P1[i]['stratum'] == s)) for s in sorted({P1[i]['stratum'] for i in ids})},
           'job_class': {'%s|%s' % i: out[i] for i in ids}, 'checks': {'%s|%s' % i: c for i, c in checks.items()},
           'listed': {k: (len(v)) for k, v in listed.items()}, 'listed_items': listed,
           'rerun_R': len(R)}
    (D / 'CLASSIFY.json').write_text(json.dumps(res, indent=1, default=str) + '\n')
    print(json.dumps({k: res[k] for k in ('cache', 'jobs', 'classes', 'listed', 'rerun_R')}))
    bad = [v for v in out.values() if v.startswith(('failure:', 'stop:'))]
    sys.exit(3 if bad else 0)


if __name__ == '__main__':
    main()
