"""F-DYN v3 certificates (Leo's workload, verified by Nora at 7eb3691) — contact relaxation only.

SCENARIO from a reconstruction; not the 2025 fire. Dose binds over 5–8 h (Nora): a ROUTE certificate here proves
only that no journey arrives sooner; NO_ROUTE still implies full-policy no-route. Roads are the recorded clipped
windows re-indexed onto the full grid (45% of burned cells have no modelled roads).

Per packet (built from MANIFEST_v3.json commands in a worktree of leo/f-c1-see-before-leave):
  * P1: per-cell flame sets from HAZARD.json vs own raw-array derivation vs ContactModel; differences classified
    (float-sum end vs exact-rational end) and their effect on the integer instance of the first origin;
  * every origin of the matching INSTANCE.json entry at each departure: forward CERT + COCERT size, both checkers;
  * O2: derive_instance vs build_instance on the first origin (every edge, own geometry).
Usage: python fdyn_certs.py --leo LEO_WORKTREE --packets REL_DIR... --departures 0 7200 --out DIR --c-checker PATH
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import derive_instance as DI  # noqa: E402
import generate as G  # noqa: E402
import p1_check as P  # noqa: E402
from wfg_scenario_members.contact import ContactModel  # noqa: E402
from wfg_sipp.frontend import build_instance, prepared  # noqa: E402


def run(cmd, path):
    """Checker stdout and wall time. An empty stdout is a failure to RUN the checker (seen on 69 rows of the first F-DYN batch while
    another job ran; the cause is unknown because exit status and stderr were not kept), not a verdict: retry once, and if it is still
    empty return 'NORUN exit=<code> <last stderr line>' so it can never be mistaken for ACCEPT or REJECT."""
    for _ in range(2):
        t0 = time.perf_counter()
        p = subprocess.run(cmd + [str(path)], capture_output=True, text=True)
        out = p.stdout.strip()
        if out:
            break
    if not out:
        out = "NORUN exit=%s %s" % (p.returncode, (p.stderr.strip().splitlines() or [""])[-1][:200])
    return out, round(time.perf_counter() - t0, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leo", required=True)
    ap.add_argument("--packets", nargs="+", required=True)
    ap.add_argument("--departures", type=int, nargs="+", default=[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--c-checker", required=True)
    a = ap.parse_args()
    L = Path(a.leo) / "research/harness-2026-11/F-DYN/_data"
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    instances = json.loads((L / "INSTANCE.json").read_text())["instances"]
    graphs, rows, packets = {}, [], []
    for rel in a.packets:
        pk = Path(a.leo) / rel
        name = pk.name                                   # <start>_h<H>_<variant>_central_q300
        region = pk.parent.name
        start = name.split("_")[0]
        H = int(name.split("_h")[1].split("_")[0]) * 3600
        variant = "kriged_mean" if "_kriged_mean_" in name else "firms_early" if "_firms_early_" in name else "envelope"
        # origins are the region's entry nodes (same for every start of a region and horizon); a synthetic start has no
        # entry of its own, so use the region/horizon entry and record it (prow["origins_from"])
        same = [i for i in instances if i["region"] == region and i["horizon_s"] == H]
        entry = next((i for i in same if i["start_tag"] == start), same[0])
        if region not in graphs:
            g = json.loads((L / "graphs_interim" / region / "graph.json").read_text())
            graphs[region] = (g, prepared(g))
        g, pg = graphs[region]
        hz_bytes = (pk / "HAZARD.json").read_bytes()
        hz = json.loads(hz_bytes)
        Hs = F(float(hz["valid_until"]))
        model = ContactModel.from_packet(pk)
        A = {k: v for k, v in P.from_hazard(hz, Hs).items() if v}
        B = {k: v for k, v in P.from_raw(pk, Hs).items() if v}
        C = {k: v for k, v in ((k, P.merge(v, F(0), Hs)) for k, v in model.cell_intervals.items()) if v}
        d_hc = [k for k in set(A) | set(C) if A.get(k) != C.get(k)]
        float_end = sum(1 for k in d_hc if len(A.get(k, [])) == len(C.get(k, [])) and all(
            x0 == y0 and x1 >= y1 and x1 - y1 < F(1, 10**6) for (x0, x1), (y0, y1) in zip(A[k], C[k])))
        prow = dict(packet=rel, region=region, start=start, horizon_s=H, variant=variant,
                    hazard_sha256=hashlib.sha256(hz_bytes).hexdigest(), active_cells=len(C),
                    p1_raw_vs_contact=sum(B.get(k) != C.get(k) for k in set(B) | set(C)),
                    p1_hazard_vs_contact=len(d_hc), p1_hazard_later_end_by_lt_1us=float_end, origins_from=entry["start_tag"])
        o0 = entry["origins"][0]

        def req(o, dep):
            return {"position": {"node": o["entry_node"]}, "incoming_edge": None, "departure": dep, "horizon": H,
                    "destinations": [{"node": d["node"], "dwell": d["dwell_s"], "open_intervals": [[0, H]]} for d in o["destinations"]]}

        class HzModel:
            cell_intervals = A
            supported = True
        ih_a, _ = build_instance(g, req(o0, a.departures[0]), HzModel, prepared_graph=pg)
        ih_c, _ = build_instance(g, req(o0, a.departures[0]), model, prepared_graph=pg)
        prow["p1_integer_instance_equal_first_origin"] = (ih_a.edge_block, ih_a.wait_block, ih_a.accept) == (ih_c.edge_block, ih_c.wait_block, ih_c.accept)
        t0 = time.perf_counter()
        prow["o2_diffs_first_origin"] = len(DI.compare(ih_c, DI.derive(g, req(o0, a.departures[0]), model.cell_intervals)))
        prow["o2_s"] = round(time.perf_counter() - t0, 1)
        packets.append(prow)
        print(json.dumps(prow), flush=True)
        for o in entry["origins"]:
            for dep in a.departures:
                inst, _ = build_instance(g, req(o, dep), model, prepared_graph=pg)
                t0 = time.perf_counter()
                claim, T, text, ih, st = G.certify(inst)
                cs = time.perf_counter() - t0
                inst_bytes = len(G.instance_text(inst))
                t0 = time.perf_counter()
                co, _, cst = G.cocert_bundle(inst, claim=claim, T=T, legs=[])
                cos = time.perf_counter() - t0
                p = out / ("%s__%s__%s__d%d.wfgc" % (region, name, o["origin_id"].replace("/", "_").replace(":", "_"), dep))
                p.write_text(text)
                c, c_s = run([a.c_checker], p)
                py, py_s = run([sys.executable, str(HERE / "check_py.py")], p)
                p.unlink()                                 # keep disk use bounded; sizes are recorded
                row = dict(packet=name, region=region, variant=variant, horizon_s=H, origin=o["origin_id"], departure=dep,
                           claim=claim, T=T, states=st["states"], r_intervals=st["r_intervals"], instance_bytes=inst_bytes,
                           cert_bytes=len(text) - inst_bytes, co_cert_bytes=len(co) - inst_bytes, co_states=cst["co_states"],
                           blocked_edges=len(inst.edge_block), certify_s=round(cs, 2), cocert_s=round(cos, 2),
                           c=c, c_s=c_s, py=py, py_s=py_s,
                           agree=c.split()[:2] == py.split()[:2] and c.startswith("ACCEPT"))
                rows.append(row)
                if not row["agree"]:
                    print("DISAGREE", json.dumps(row), flush=True)
        print(json.dumps({"packet": name, "done_rows": len(rows)}), flush=True)
        (out / "FDYN.json").write_text(json.dumps({"packets": packets, "rows": rows}, indent=1) + "\n")


if __name__ == "__main__":
    main()
