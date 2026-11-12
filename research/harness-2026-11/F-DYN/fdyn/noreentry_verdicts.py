"""NOREENTRY_RULE.md acceptance 7 (reported, not asserted): requests whose dose or peak verdict differs between the
reopening and the no-re-entry packet of one MANIFEST_v3_6 entry.

Requests: fdyn/requests.py requests_for(entry, INSTANCE, HAZARD, graph nodes), built per packet (member ids differ).
Per request (origin, departure):
  * solve on each packet with the unchanged router (routing-package routing.core.solve);
  * every route found (on either packet) is checked on BOTH packets with routing.independent.check_route;
  * the request's dose/peak verdict on a packet, for that route = the set {PEAK_BUDGET, DOSE_BUDGET} & codes;
  * a request counts as "dose/peak verdict differs" when, for some route found, that set differs between packets.
Contact differences (FLAME_CONTACT) are expected (no re-entry blocks more) and are reported separately, not counted.

    python3 research/harness-2026-11/F-DYN/fdyn/noreentry_verdicts.py --entry REGION:START:H:VARIANT [--limit N] --out F.json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'routing-package'))
sys.path.insert(0, str(HERE.parent))
from routing.core import solve  # noqa: E402
from routing.independent import check_route  # noqa: E402
from fdyn.requests import requests_for  # noqa: E402

MAN = REPO / 'research/harness-2026-11/F-DYN/MANIFEST_v3_6.json'
INST = REPO / 'research/harness-2026-11/F-DYN/_data/INSTANCE.json'
DP = {'PEAK_BUDGET', 'DOSE_BUDGET'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--entry', required=True)
    ap.add_argument('--limit', type=int, default=None, help='first N requests only (stated in the output)')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    key = tuple(a.entry.split(':'))
    man = json.loads(MAN.read_text())
    pick = [e for e in man['entries'] if (e['region'], e['start'], str(e['horizon_h']), e['variant']) == key]
    pk = {e['transform']: e for e in pick}
    insts = {(i['region'], int(i['horizon_s'])): i for i in json.loads(INST.read_text())['instances']}
    gpath = REPO / pk['reopening']['cmd'][pk['reopening']['cmd'].index('--graph') + 1]
    graph = json.loads(gpath.read_text())
    nodes = {n['id'] for n in graph['nodes']}
    hz, reqs = {}, {}
    for t in ('reopening', 'no_reentry/1'):
        hz[t] = json.loads((REPO / pk[t]['out'] / 'HAZARD.json').read_text())
        inst = insts[(key[0], int(float(key[2]) * 3600))]
        reqs[t] = requests_for(pk[t], inst, hz[t], nodes)
    n = len(reqs['reopening']) if a.limit is None else min(a.limit, len(reqs['reopening']))
    status = {t: collections.Counter() for t in hz}
    differs, contact_only, rows = 0, 0, []
    t0 = time.time()
    for i in range(n):
        (k_re, q_re), (k_nr, q_nr) = reqs['reopening'][i], reqs['no_reentry/1'][i]
        assert (k_re['origin_id'], k_re['departure_s']) == (k_nr['origin_id'], k_nr['departure_s'])
        res = {'reopening': solve(graph, hz['reopening'], q_re), 'no_reentry/1': solve(graph, hz['no_reentry/1'], q_nr)}
        for t, r in res.items():
            status[t][r['status']] += 1
        d, c = False, False
        for t, r in res.items():
            if not r['legs']:
                continue
            ck = {u: check_route(graph, hz[u], {'reopening': q_re, 'no_reentry/1': q_nr}[u], r['legs'], r['destination'])
                  for u in hz}
            dp = {u: sorted(DP & set(v['codes'])) for u, v in ck.items()}
            fl = {u: 'FLAME_CONTACT' in v['codes'] for u, v in ck.items()}
            d |= dp['reopening'] != dp['no_reentry/1']
            c |= fl['reopening'] != fl['no_reentry/1']
        differs += d
        contact_only += (c and not d)
        rows.append({'origin_id': k_re['origin_id'], 'departure_s': k_re['departure_s'],
                     'status': {t: r['status'] for t, r in res.items()}, 'dose_peak_differs': d, 'contact_differs': c})
    out = {'rule': 'NOREENTRY_RULE.md acceptance 7 (reported, not asserted)', 'entry': a.entry, 'requests': n,
           'requests_total': len(reqs['reopening']), 'limited': a.limit is not None,
           'dose_or_peak_verdict_differs': differs, 'contact_differs_only': contact_only,
           'status_counts': {t: dict(v) for t, v in status.items()}, 'wall_s': round(time.time() - t0, 1), 'rows': rows}
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
