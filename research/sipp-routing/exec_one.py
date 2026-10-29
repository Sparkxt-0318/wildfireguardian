"""One timed execution in a fresh interpreter: load graph, packet and request, run one planner, print one JSON line.

  python -I exec_one.py --planner sweep|sipp --region R --cutoff TAG --event E --mission M [--members first:K --exports DIR]
"""
import argparse
import json
import resource
import sys
import time
from pathlib import Path

T0 = time.perf_counter()
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
sys.path.insert(0, str(REPO / "experimental" / "scenario-members"))
sys.path.insert(0, str(REPO / "experimental" / "sipp-routing" / "src"))


def main():
    ap = argparse.ArgumentParser()
    for k in ("--planner", "--region", "--cutoff", "--event", "--mission"):
        ap.add_argument(k, required=True)
    ap.add_argument("--members", default="v1")
    ap.add_argument("--exports", default=None)
    ap.add_argument("--wall", type=float, default=30.0)
    a = ap.parse_args()
    from wfg_members import kit, planner
    from wfg_members.contact import ContactModel
    from wfg_sipp import frontend
    kit.install()
    t_imp = time.perf_counter()
    p = kit.paths(a.region, a.cutoff, a.event, a.mission)
    graph = json.loads(p["graph"].read_text())
    req = json.loads(p["request"].read_text())
    model = ContactModel.from_packet(p["packet"])
    if a.members != "v1":
        import numpy as np
        import bridge_v2 as B2
        K = int(a.members.split(":")[1])
        with np.load(Path(a.exports) / a.event / ("FORECAST_%s.npz" % a.cutoff)) as z:
            fbh = z["trajectory_first_burn_hour"]
        md = json.loads((p["packet"] / "NATIVE_METADATA.json").read_text())
        win = B2.frozen_window(p["packet"])
        ev = B2.ignition_seconds(fbh, range(K), timing="uniform")
        if win is not None:
            ev = ev[:, win["r0"]:win["r1"] + 1, win["c0"]:win["c1"] + 1]
        H, W = md["shape"]
        from fractions import Fraction as F
        events = []
        for s in range(K):
            flat = ev[s].ravel()
            idx = np.flatnonzero(np.isfinite(flat))
            events.append({(H - 1 - int(i) // W) * W + int(i) % W: F(float(flat[i])) for i in idx})
        model = model.with_events(events, ["t%d" % k for k in range(K)])
        req = B2.rekey_request_k(req, model.ids, kit.cutoff_iso(a.cutoff))
    t_load = time.perf_counter()
    fn = planner.sweep_plan if a.planner == "sweep" else frontend.sipp_plan
    res = fn(graph, req, model, wall_s=max(0.0, a.wall - (time.perf_counter() - T0)))
    t_end = time.perf_counter()
    m = res.get("metrics", {})
    print(json.dumps({"planner": a.planner, "region": a.region, "cutoff": a.cutoff, "mission": a.mission, "members": a.members,
                      "raw_status": res["raw_status"], "status": res["status"], "arrival": res["arrival"],
                      "legs": len(res["legs"]), "complete_s": t_end - T0, "import_s": t_imp - T0, "load_s": t_load - t_imp,
                      "planner_s": res["wall_s"], "states": m.get("states_reached", m.get("expansions")),
                      "pieces": m.get("pieces"), "expansions": m.get("expansions"), "sweep_seconds": m.get("sweep_seconds"),
                      "build_s": m.get("build_s", m.get("static_setup_s")), "search_s": m.get("search_s"),
                      "blocked_edges": m.get("blocked_edges", m.get("contact_edges")),
                      "cells_with_activity": len(model.cell_intervals), "member_count": len(model.ids),
                      "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0}))


if __name__ == "__main__":
    main()
