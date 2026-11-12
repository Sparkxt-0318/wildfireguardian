"""Nora: lever-A rescues -> field witness -> kit ffi_independent_checker (cert-level, independent code)."""
import json, sys, importlib.util
from pathlib import Path
W, F, P, LEV, REGION, START, HS = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6], int(sys.argv[7])
sys.path.insert(0, str(W)); sys.path.insert(0, str(W / 'research/harness-2026-11/F-3.1'))
from deadline_field.real import PacketModel
from deadline_field.core import backward, witness, issue_set
from deadline_field import intervals as iv
spec = importlib.util.spec_from_file_location('ffi', W / 'integration/kit/runner/ffi_independent_checker.py'); ffi = importlib.util.module_from_spec(spec); spec.loader.exec_module(ffi)
gp = F / f'_data/graphs_interim/{REGION}/graph.json'
pm = PacketModel(gp, P); hz = json.loads((P / 'HAZARD.json').read_text()); mem = [m['id'] for m in hz['members']]
G = ffi.Graph(json.loads(gp.read_text())); PK = ffi.Packet(P, G)
I = next(i for i in json.load(open(F / '_data/INSTANCE.json'))['instances'] if i['region'] == REGION and i['horizon_s'] == HS and i['start_tag'] == START)
lev = json.load(open(LEV))
def req(o, dep, dest, dwell):
    return {"position": {"node": o}, "incoming_edge": None, "departure": dep, "horizon": pm.H,
            "destinations": [{"node": dest, "dwell": dwell, "open_intervals": [[0, pm.H]]}],
            "budgets": {"peak": 10.0, "dose": {m: 100.0 for m in mem}}, "incurred": {m: 0.0 for m in mem},
            "exposure_scope": "including_dwell", "objective": "earliest_arrival"}
legs_of = lambda w: [{"kind": "EDGE", "edge": pm.g.edge_ids[x], "start": a, "end": b, "from_fraction": 0, "to_fraction": 1} if kd == "EDGE" else {"kind": "WAIT", "node": pm.node_ids[x], "start": a, "end": b} for kd, x, a, b in w[1]]
for s, blk in lev['primary'].items():
    dep = lev['t_ref_s'] - int(s) * 60
    for oid, r in blk['rows'].items():
        if r['class'] not in ('A_only', 'both'): continue
        o = next(x for x in I['origins'] if x['origin_id'] == oid); e = o['entry_node']
        for d in o['destinations']:
            fld = backward(pm.instance('cert', [{"node": d['node'], "dwell": d['dwell_s'], "window": [0, pm.H]}], [e]))
            if not iv.contains(issue_set(fld, pm.nidx[e]), dep): continue
            w = witness(fld, pm.nidx[e], dep)
            c = ffi.check(G, PK, req(e, dep, d['node'], d['dwell_s']), legs_of(w), d['node'])['classification']
            print(json.dumps({"shift_min": s, "origin": oid, "dep": dep, "dest": d['node'], "field_arrival": w[0], "ffi_overall": c['overall'], "whole_road": c['whole_road_contact'], "contradictions": c['contradictions']}), flush=True)
            break
