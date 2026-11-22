"""Nora: Richard #14 return trips -> kit ffi_independent_checker. (a) return_not_checked: checker with no witness on the
return request (infeasibility by independent code); (b) outbound = earliest own destination: field witness to each own
destination at t = 0, each judged by the checker (certified optimal arrival), argmin vs the claimed outbound destination."""
import json, sys, importlib.util
from pathlib import Path
W, F, P, OUT, REGION, START, HS, NB = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6], int(sys.argv[7]), int(sys.argv[8])
sys.path.insert(0, str(W)); sys.path.insert(0, str(W / 'research/harness-2026-11/F-3.1'))
from deadline_field.real import PacketModel
from deadline_field.core import backward, witness, issue_set
from deadline_field import intervals as iv
spec = importlib.util.spec_from_file_location('ffi', W / 'integration/kit/runner/ffi_independent_checker.py'); ffi = importlib.util.module_from_spec(spec); spec.loader.exec_module(ffi)
gp = F / f'_data/graphs_interim/{REGION}/graph.json'
pm = PacketModel(gp, P); mem = [m['id'] for m in json.loads((P / 'HAZARD.json').read_text())['members']]
G = ffi.Graph(json.loads(gp.read_text())); PK = ffi.Packet(P, G)
I = next(i for i in json.load(open(F / '_data/INSTANCE.json'))['instances'] if i['region'] == REGION and i['horizon_s'] == HS and i['start_tag'] == START)
out = json.load(open(OUT))
def req(o, dep, dest, dwell):
    return {"position": {"node": o}, "incoming_edge": None, "departure": dep, "horizon": pm.H,
            "destinations": [{"node": dest, "dwell": dwell, "open_intervals": [[0, pm.H]]}],
            "budgets": {"peak": 10.0, "dose": {m: 100.0 for m in mem}}, "incurred": {m: 0.0 for m in mem},
            "exposure_scope": "including_dwell", "objective": "earliest_arrival"}
legs_of = lambda w: [{"kind": "EDGE", "edge": pm.g.edge_ids[x], "start": a, "end": b, "from_fraction": 0, "to_fraction": 1} if kd == "EDGE" else {"kind": "WAIT", "node": pm.node_ids[x], "start": a, "end": b} for kd, x, a, b in w[1]]
seen = set()
for dl in ('30', '60', '120'):
    for oid, r in sorted(out['origins'].items()):
        x = r.get('return', {}).get(dl)
        if not x or x['class'] != 'return_not_checked' or (oid, x['depart']) in seen: continue
        seen.add((oid, x['depart']))
        c = ffi.check(G, PK, req(r['outbound_dest'], x['depart'], r['entry_node'], 0), None, None)['classification']
        print(json.dumps({"a_delta": dl, "origin": oid, "from": r['outbound_dest'], "depart": x['depart'], "ffi_no_witness": c['overall']}), flush=True)
k = 0
for oid, r in sorted(out['origins'].items()):
    if not r.get('outbound_dest') or k >= NB: continue
    k += 1
    o = next(x for x in I['origins'] if x['origin_id'] == oid); e = o['entry_node']; res = {}
    for d in o['destinations']:
        fld = backward(pm.instance('cert', [{"node": d['node'], "dwell": d['dwell_s'], "window": [0, pm.H]}], [e]))
        if not iv.contains(issue_set(fld, pm.nidx[e]), 0): res[d['node']] = None; continue
        w = witness(fld, pm.nidx[e], 0)
        c = ffi.check(G, PK, req(e, 0, d['node'], d['dwell_s']), legs_of(w), d['node'])['classification']
        res[d['node']] = (w[0], c['overall'], c['whole_road_contact'])
    ok = {n: v[0] for n, v in res.items() if v and v[1] == 'INDEPENDENTLY_CERTIFIED_OPTIMAL'}
    pick = min(ok.items(), key=lambda t: (t[1], t[0]))[0] if ok else None
    print(json.dumps({"b_origin": oid, "claimed": [r['outbound_dest'], r['arrival']], "per_dest": res, "argmin_certified": pick, "match": pick == r['outbound_dest']}), flush=True)
