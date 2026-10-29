"""Extended-horizon exploratory panel (3 h and 6 h), NOT frozen missions; never pooled with the frozen counts.

Question: once trajectories span several hourly updates, do coherent trajectory members change routing decisions
compared with members drawn independently per cell from the same per-cell first-burn-hour marginals (the independent law
at that horizon)? Truth = withheld trajectories of the same rollout.

Modes
  fixture  FIXTURE data root (research/scenario-members/fixture_data_root.py --large), a synthetic grid road network and
           four synthetic 1 h source missions; every output is labelled FIXTURE and describes no real fire.
  real     the 20 frozen Korean missions derived to 3 h and 6 h (derive_extended_missions.py) with model-mode export v3
           at 6 h on the real data tree (pending: the environmental rasters are not on this host).

Laws (same K, same timing rule, uniform within the hour)
  trajectory           the first K trajectories of the pool (0..pool-1).
  independent_marginal for every cell independently, a first-burn hour drawn from the empirical marginal of the pool
                       (seed recorded); same expected burned area, no spatial or temporal coherence.

  python research/synthetic-truth/run_extended_panel.py --mode fixture --export DIR --out research/synthetic-truth/data/extended_panel
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import platform
import sys
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "synthetic-truth" / "src"))
from wfg_osse import harness, truth as TR  # noqa: E402
import bridge_v2 as B2  # noqa: E402
from wfg_members import coverage, extended, kit  # noqa: E402
from wfg_members.contact import ContactModel  # noqa: E402
from wfg_sipp.frontend import sipp_plan  # noqa: E402

POOL, HOLDOUT, K, SEED = 256, list(range(256, 356)), 8, 20261030


def fixture_graph(shape, transform, step=2, lo=20, hi=60):
    """Grid road network on the fixture grid: a node at every `step`-th cell centre of rows/columns lo..hi, two-way
    edges between neighbours (750 m at 15 m/s = 50 s), every fourth node waitable, U-turns forbidden."""
    H, W = shape
    res = transform[0]
    x0, ytop = transform[2], transform[5]
    y0 = ytop - H * res
    nodes, edges, idx = [], [], {}
    for gr in range(lo, hi + 1, step):
        for c in range(lo, hi + 1, step):
            nid = "f%d_%d" % (gr, c)
            idx[(gr, c)] = nid
            nodes.append({"id": nid, "x": x0 + (c + 0.5) * res, "y": y0 + (gr + 0.5) * res,
                          "waitable": ((gr // step) + (c // step)) % 4 == 0})
    forbidden = []
    for (gr, c), nid in idx.items():
        for dr, dc in ((step, 0), (0, step)):
            other = idx.get((gr + dr, c + dc))
            if other:
                a, b = "e_%s_%s" % (nid, other), "e_%s_%s" % (other, nid)
                edges.append({"id": a, "u": nid, "v": other, "travel_ticks": 50})
                edges.append({"id": b, "u": other, "v": nid, "travel_ticks": 50})
                forbidden += [[a, b], [b, a]]
    return {"nodes": nodes, "edges": edges, "forbidden_turns": forbidden, "crs": "EPSG:5179", "revision": "FIXTURE",
            "grid": {"x0": x0, "y0": y0, "resolution": res, "width": W, "height": H}}


def fixture_sources():
    """Four synthetic 1 h source missions crossing the fixture fire (graph rows are south-up)."""
    def req(o, d):
        return {"position": {"node": o}, "incoming_edge": None, "departure": 0, "horizon": 3600.0,
                "destinations": [{"node": d, "dwell": 120, "open_intervals": [[0, 3600]]}], "incurred": {"m": 0},
                "hazard_version": 1, "objective": "earliest_arrival", "exposure_scope": "including_dwell",
                "budgets": {"peak": 10, "dose": {"m": 100}}, "limits": {"wall_s": 30}, "solver": "baseline"}
    return {"FX_A": req("f40_20", "f40_60"), "FX_B": req("f30_20", "f50_60"), "FX_C": req("f20_30", "f60_34"),
            "FX_D": req("f50_24", "f28_56")}


def graph_events(ev, shape):
    H, W = shape
    out = []
    for s in range(ev.shape[0]):
        flat = ev[s].ravel()
        idx = np.flatnonzero(np.isfinite(flat))
        out.append({(H - 1 - int(i) // W) * W + int(i) % W: F(float(flat[i])) for i in idx})
    return out


def independent_marginal(fbh_pool, hours, count, seed):
    """[count,H,W] first-burn hours drawn independently per cell from the pool's empirical marginal over {1..hours, never}."""
    rng = np.random.default_rng(seed)
    N = fbh_pool.shape[0]
    probs = [(fbh_pool == h).sum(axis=0) / N for h in range(1, hours + 1)]
    cum = np.cumsum(probs, axis=0)
    u = rng.random((count,) + fbh_pool.shape[1:])
    out = np.full((count,) + fbh_pool.shape[1:], -1, dtype=np.int16)
    for h in range(hours, 0, -1):
        out[u < cum[h - 1][None]] = h
    out[:, (fbh_pool[0] == 0)] = 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("fixture", "real"), required=True)
    ap.add_argument("--export", required=True, help="export v3 folder with v2_staging (model mode, 6 h)")
    ap.add_argument("--event", default="FIX_01")
    ap.add_argument("--cutoff", default="20000101T030000Z")
    ap.add_argument("--out", default=str(HERE / "data" / "extended_panel"))
    a = ap.parse_args()
    if a.mode == "real":
        raise SystemExit("real mode needs model-mode exports at 6 h on the real data tree; not available on this host yet")
    K_ = kit.install()
    exp = Path(a.export)
    rec = json.loads((exp / ("FORECAST_RECORD_%s.json" % a.cutoff)).read_text())
    with np.load(exp / ("FORECAST_%s.npz" % a.cutoff)) as z:
        fbh = z["trajectory_first_burn_hour"].copy()
    if rec["trajectory_horizon_hours"] < 6 or fbh.shape[0] < max(HOLDOUT) + 1:
        raise SystemExit("need a 6 h export with at least %d trajectories" % (max(HOLDOUT) + 1))
    fc = B2.load_export(exp / "v2_staging" / ("FORECAST_%s.npz" % a.cutoff), exp / "v2_staging" / ("FORECAST_RECORD_%s.json" % a.cutoff))[0]
    T = float(fc["contract__cell_duration_s"])
    st = K_["bridge"].settings_for(T)
    st["scenario_count"] = 1
    base = K_["bridge"].construct(fc, cutoff_utc=kit.cutoff_iso(a.cutoff), epsg=5179, settings=st)
    shape = base["shape"]
    transform = [float(v) for v in fc["affine_transform"]]
    graph = fixture_graph(shape, transform)
    proto = ContactModel.from_arrays(np.full((1,) + shape, np.inf), base["current"], T, base["remaining_s"], ids=["p"])
    kern = coverage.Kernels(transform, st, 5179, shape)
    cur_flux = kern.of_mask(base["current"])
    rows, laws_meta = [], {}
    t_all = time.perf_counter()
    for H in extended.HORIZONS:
        hours = H // 3600
        traj_ev = B2.ignition_seconds(fbh, list(range(K)), horizon_s=H)
        ind_fbh = independent_marginal(fbh[:POOL], hours, K, SEED + hours)
        ind_ev = B2.ignition_seconds(ind_fbh, list(range(K)), horizon_s=H)
        truth_ev = B2.ignition_seconds(fbh, HOLDOUT, horizon_s=H)
        truths = [TR.Truth("holdout_trajectory", "trajectory_%d" % j, e, list(proto.current), proto.R, proto.T,
                           {"trajectory_index": j}) for j, e in zip(HOLDOUT, graph_events(truth_ev, shape))]
        for law, ev in (("trajectory", traj_ev), ("independent_marginal", ind_ev)):
            model = proto.with_events(graph_events(ev, shape), ["%s:%d" % (law, k) for k in range(K)], label=law)
            laws_meta["%s_H%d" % (law, hours)] = {"ignitions_per_member": model.new_ignition_counts()}
            for name, src in fixture_sources().items():
                req0, prov = extended.derive(src, H, source_name="FIXTURE source " + name)
                req = B2.rekey_request_k(req0, model.ids, kit.cutoff_iso(a.cutoff))
                shared = sipp_plan(graph, req, model.shared_only())
                t0 = time.perf_counter()
                dec = harness.decide(graph, req, model, kernels=kern, current_flux=cur_flux)
                wall = time.perf_counter() - t0
                for r in harness.score_against(graph, req, dec, truths, cutoff=a.cutoff, region="FIXTURE", mission=name,
                                               forecast_source=law, shared_route=shared, kernels=kern, current_flux=cur_flux):
                    r.update({"panel": extended.LABEL, "data": "FIXTURE", "horizon_s": H, "members": K, "law": law,
                              "decision_wall_s": wall, "derivation": prov, "reason": dec["reason"]})
                    rows.append(r)
                print(json.dumps({"H": hours, "law": law, "mission": name, "verdict": dec["verdict"], "arrival": dec["arrival_s"],
                                  "fs": sum(1 for r in rows[-len(truths):] if r["false_safe"]),
                                  "fr": sum(1 for r in rows[-len(truths):] if r["false_refusal"])}), flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out / "FIXTURE_extended_records.jsonl.gz", "wt") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    (out / "FIXTURE_run.json").write_text(json.dumps({
        "label": "FIXTURE " + extended.LABEL, "export_record_npz_sha256": rec["npz_sha256"], "trajectory_count": int(fbh.shape[0]),
        "pool": POOL, "holdout": [HOLDOUT[0], HOLDOUT[-1]], "K": K, "independent_seed_base": SEED, "laws": laws_meta,
        "graph_nodes": len(graph["nodes"]), "graph_edges": len(graph["edges"]), "wall_s": time.perf_counter() - t_all,
        "host": {"platform": platform.platform(), "loadavg": os.getloadavg()}}, indent=1) + "\n")


if __name__ == "__main__":
    main()
