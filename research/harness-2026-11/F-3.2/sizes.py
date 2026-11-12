"""Size study: forward CERT vs backward COCERT bundles (raw and gzip -9), plus forward/backward disjointness below T.
Usage: python sizes.py --out DIR   (writes DIR/*.co.wfgc and results/sizes_py<ver>.json)"""
import argparse, gzip, json, os, subprocess, sys, time
from pathlib import Path
HERE = Path(os.path.abspath(__file__)).parent
sys.path.insert(0, str(HERE))
import cases, generate as G
from wfg_scenario_members.contact import ContactModel
from wfg_sipp.frontend import build_instance

ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
rows = []
for c in cases.korean_cases():
    g = json.loads(Path(c["graph"]).read_text()); r = json.loads(Path(c["request"]).read_text())
    inst, _ = build_instance(g, r, ContactModel.from_packet(c["packet"]))
    res = G.S.solve(inst)
    claim, T, legs = ("ROUTE", res["arrival"], res["legs"]) if res["status"] == "FOUND" else ("NO_ROUTE", inst.horizon + 1, [])
    R, A = G.reachable(inst, T)
    fwd, ih = G.certificate_bundle(inst, claim=claim, T=T, legs=legs, R=R, A=A)
    t0 = time.perf_counter(); co, ih2, cst = G.cocert_bundle(inst, claim=claim, T=T, legs=legs); co_s = time.perf_counter() - t0
    Gr, Ga = G.coreachable(inst, T)
    overlap = sum(len(G.minus(R[s], G.minus(R[s], Gr.get(s, [])))) for s in R)   # |R_s ∩ Gr_s| interval count
    inst_bytes = len(G.instance_text(inst))
    p = out / (c["region"] + "__" + c["mission"] + ".co.wfgc"); p.write_text(co)
    t1 = time.perf_counter()
    chk = subprocess.run([sys.executable, str(HERE / "check_py.py"), str(p)], capture_output=True, text=True).stdout.strip()
    row = dict(mission=c["mission"], claim=claim, T=T, instance_bytes=inst_bytes,
               fwd_cert_bytes=len(fwd) - inst_bytes, co_cert_bytes=len(co) - inst_bytes,
               fwd_gzip=len(gzip.compress(fwd.encode(), 9)), co_gzip=len(gzip.compress(co.encode(), 9)),
               inst_gzip=len(gzip.compress(G.instance_text(inst).encode(), 9)),
               fwd_states=len(R), co_states=cst["co_states"], forward_backward_overlap_intervals=overlap,
               cocert_generate_s=round(co_s, 2), check_py_cocert=chk, check_py_s=round(time.perf_counter() - t1, 2))
    rows.append(row); print(json.dumps(row), flush=True)
(HERE / "results" / ("sizes_py%d%d.json" % sys.version_info[:2])).write_text(json.dumps(rows, indent=1) + "\n")
