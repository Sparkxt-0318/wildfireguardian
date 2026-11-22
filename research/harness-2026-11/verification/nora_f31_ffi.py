"""Nora: regenerate F-3.1 witnesses with the field and judge them with the kit's ffi_independent_checker (no routing imports)."""
import json, sys, importlib.util
from pathlib import Path
W = Path(sys.argv[1]); out = json.load(open(sys.argv[2])); mode = sys.argv[3]; k = int(sys.argv[4])
sys.path.insert(0, str(W)); sys.path.insert(0, str(W/'research/harness-2026-11/F-3.1'))
from deadline_field.real import PacketModel
from deadline_field.core import backward, witness
spec = importlib.util.spec_from_file_location('ffi', W/'integration/kit/runner/ffi_independent_checker.py'); ffi = importlib.util.module_from_spec(spec); spec.loader.exec_module(ffi)
region, compact = out['region'], out['input_time'].replace('-','').replace(':','')
gp = W/'data/routing/graphs'/region/'graph.json'; pdir = W/'data/routing/latest_inputs_try02/packets'/region/compact
pm = PacketModel(gp, pdir); hz = json.loads((pdir/'HAZARD.json').read_text()); mem = [m['id'] for m in hz['members']]
G = ffi.Graph(json.loads(gp.read_text())); PK = ffi.Packet(pdir, G)
def req(o, dep, dest, dwell, win):
    return {"position": {"node": o}, "incoming_edge": None, "departure": dep, "horizon": pm.H,
            "destinations": [{"node": dest, "dwell": dwell, "open_intervals": [list(win)]}],
            "budgets": {"peak": 10.0, "dose": {m: 100.0 for m in mem}}, "incurred": {m: 0.0 for m in mem},
            "exposure_scope": "including_dwell", "objective": "earliest_arrival"}
def legs_of(w):
    return [{"kind":"EDGE","edge":pm.g.edge_ids[x],"start":a,"end":b,"from_fraction":0,"to_fraction":1} if kd=="EDGE" else {"kind":"WAIT","node":pm.node_ids[x],"start":a,"end":b} for kd,x,a,b in w[1]]
cases = []
if mode == 'deadline':
    for r in sorted(out['deadline_witness_checks'], key=lambda r: -(r['max_dose'] or 0))[:k]:
        cases.append((r['origin'], r['dest'], 120, r['window'], r['deadline_s'], r['arrival'], True))
else:   # resolved UNRESOLVED jobs
    for r in [j for j in out['jobs'] if j['verdict'] not in ('checked_route','model_no_route') and j['field']['cert']['feasible']][:k]:
        cases.append((r['start'], r['dest'], r['dwell'], r['window'], r['offset'], r['field']['cert']['arrival'], False))
for o, d, dwell, win, dep, arr, nxt in cases:
    inst = pm.instance('cert', [{"node": d, "dwell": dwell, "window": list(win)}], [o]); fld = backward(inst)
    w = witness(fld, pm.nidx[o], dep)
    res = ffi.check(G, PK, req(o, dep, d, dwell, win), legs_of(w), d)
    c = res['classification']
    line = {"origin": o, "dest": d, "dep": dep, "field_arrival": w[0], "claimed_arrival": arr, "ffi_overall": c['overall'], "ffi_whole_road": c['whole_road_contact'], "contradictions": c['contradictions'], "ffi_arrival": res.get("grammar",{}).get("arrival"), "grammar_errors": res.get("grammar",{}).get("errors"), "notes": res.get("grammar",{}).get("notes")}
    if nxt:
        r2 = ffi.check(G, PK, req(o, dep+1, d, dwell, win), None, None)
        line["ffi_dep_plus_1"] = r2['classification']['overall']
    print(json.dumps(line), flush=True)
