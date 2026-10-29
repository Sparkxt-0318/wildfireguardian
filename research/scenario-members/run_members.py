"""Track 1C-1 evidence: v1 independent members versus v2 trajectory members, scenario reduction and acceptance rules.

For each of the 15 frozen Korean windows and its missions (20 in total):
  * v1: the frozen packet (independent per-cell draws, K = 4, seed 20261008), frozen request;
  * v2 K = 4: the first four trajectories (same count, equal weights, no extremes) with "uniform" and "ordered" timing,
    so that the comparison isolates the member law;
  * v2 reduced: K in {8, 16, 32} with first_k, forward_selection and k_medoids on the edge-arrival distance, extremes
    appended, redistributed weights, uniform timing;
each under the rule `all` and `k_of_m` with k = ceil(0.9 m). Decisions use the frozen contact sweep (exact contact-only
relaxation) and the frozen centre checker per member (wfg_members.decide). Coverage of every returned route is computed
on all N = 1024 trajectories with the cheap checker. Reduction costs for K in {4, 8, 16, 32}, the three methods and the
three distances are recorded separately.

  python research/scenario-members/run_members.py --exports /path/exports_v3 --out research/scenario-members/data [--regions R ...]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import time
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experimental" / "scenario-members"))
sys.path.insert(0, str(REPO / "experimental" / "scenario-members" / "src"))
import bridge_v2 as B2  # noqa: E402
from wfg_members import acceptance as A  # noqa: E402
from wfg_members import check, coverage, decide, kit, planner, reduction  # noqa: E402
from wfg_members.contact import ContactModel  # noqa: E402

KS = (4, 8, 16, 32)
METHODS = reduction.METHODS
TIMING_SEED = B2.DEFAULT_TIMING_SEED
KMEDOIDS_SEED = 20261029


def load_traj(exports, event, tag):
    p = Path(exports) / event / ("FORECAST_%s.npz" % tag)
    rec = json.loads((Path(exports) / event / ("FORECAST_RECORD_%s.json" % tag)).read_text())
    if kit.sha256_file(p) != rec["npz_sha256"]:
        raise SystemExit("V3_EXPORT_HASH_MISMATCH %s" % p)
    with np.load(p) as a:
        return a["trajectory_first_burn_hour"].copy(), rec


def crop(arr, window):
    if window is None:
        return arr
    return arr[..., window["r0"]:window["r1"] + 1, window["c0"]:window["c1"] + 1]


def graph_events(events_native_window, shape):
    H, W = shape
    out = []
    for s in range(events_native_window.shape[0]):
        flat = events_native_window[s].ravel()
        idx = np.flatnonzero(np.isfinite(flat))
        out.append({(H - 1 - int(i) // W) * W + int(i) % W: F(float(flat[i])) for i in idx})
    return out


def binding_for(dec, travel, travel_flags, relaxed_window=None):
    """Which constraints changed the outcome relative to travel-only (Contract D)."""
    out = {"contact": None, "peak": None, "dose": None, "destination_window": None, "horizon": "not_evaluable_beyond_hazard_validity"}
    if travel["status"] != planner.ROUTE:
        return out
    t_contact = any(r["contact"] for r in travel_flags)
    t_peak = any(not r["peak_ok"] for r in travel_flags)
    t_dose = any(not r["dose_ok"] for r in travel_flags)
    changed = dec["verdict"] != decide.CHECKED or dec["arrival_s"] != travel["arrival"]
    out["contact"] = bool(changed and t_contact)
    out["peak"] = bool(changed and t_peak and dec.get("lazy_iterations", 0) > 0)
    out["dose"] = bool(changed and t_dose and (dec.get("lazy_iterations", 0) > 0 or not t_contact))
    if relaxed_window is not None:
        out["destination_window"] = bool(relaxed_window["status"] != planner.ROUTE and dec["verdict"] == decide.CHECKED) or (
            relaxed_window["status"] == planner.ROUTE and (dec["verdict"] != decide.CHECKED or relaxed_window["arrival"] != dec["arrival_s"]))
    return out


def run_window(region, tag, event, mission_names, exports, out_rows, out_costs, log):
    K_ = kit.install()
    p = kit.paths(region, tag, event)
    graph = json.loads(p["graph"].read_text())
    fc, record = B2.load_export(p["export_npz"], p["export_record"])
    T = float(fc["contract__cell_duration_s"])
    window = B2.frozen_window(p["packet"])
    v1_model = ContactModel.from_packet(p["packet"], label="v1")
    v1_hz = json.loads((p["packet"] / "HAZARD.json").read_text())
    md = json.loads((p["packet"] / "NATIVE_METADATA.json").read_text())
    shape = tuple(md["shape"])
    with np.load(p["packet"] / "constructed_arrays.npz") as a:
        current_native = a["current_active"].copy()
    fbh_full, v3rec = load_traj(exports, event, tag)
    N = fbh_full.shape[0]
    fbh_win = crop(fbh_full, window)
    events_all = B2.ignition_seconds(fbh_full, range(N), timing="uniform", timing_seed=TIMING_SEED)
    traj_model = v1_model.with_events(graph_events(crop(events_all, window), shape), ["t%d" % j for j in range(N)], label="all_N")
    missions = []
    for m in mission_names:
        req = json.loads(kit.paths(region, tag, event, m)["request"].read_text())
        travel = planner.sweep_plan(graph, req, v1_model.empty())
        missions.append((m, req, travel))
    # ---------------------------------------------------------------- distances
    t0 = time.perf_counter()
    burn_cells = set(v1_model.current) | {c for ev in traj_model.events for c in ev}
    expo = reduction.EdgeExposure(graph, burn_cells, K_["core"])
    Tq, Rq, cur = float(v1_model.T), float(v1_model.R), set(v1_model.current)
    Amat = reduction.edge_arrival_matrix(expo, [{c: float(b) for c, b in ev.items()} for ev in traj_model.events], Tq, 3600.0, cur, Rq)
    a_shared = expo.first_unsafe({}, Tq, 3600.0, cur, Rq)
    roads = decide.road_cells(graph)
    H, W = shape
    road_native = np.zeros(shape, bool)
    for c in roads:
        gr, cc = divmod(c, W)
        road_native[H - 1 - gr, cc] = True
    C = {"edge_arrival": reduction.distance_edge_arrival(Amat, expo.edge_len) if Amat.size else np.zeros((N, N)),
         "first_burn_l1": reduction.distance_first_burn_l1(fbh_win, 1),
         "road_symdiff": reduction.distance_road_symdiff(fbh_win, road_native, 1)}
    corridors, shared_first = [], []
    for m, req, travel in missions:
        eid = {e["id"]: i for i, e in enumerate(graph["edges"])}
        cols = sorted({expo.col[eid[l["edge"]]] for l in travel["legs"] if l["kind"] == "EDGE" and eid[l["edge"]] in expo.col})
        corridors.append(cols)
        shared_first.append(float(a_shared[cols].min()) if cols else math.inf)
    log["distances_s"] = time.perf_counter() - t0
    for dist, Cm in C.items():
        for method in METHODS:
            for K in KS:
                sel = reduction.reduce_members(Cm, K, method, A=Amat if Amat.size else None, corridors=corridors,
                                               shared_first=shared_first, seed=KMEDOIDS_SEED, append_extremes=False)
                selx = reduction.reduce_members(Cm, K, method, A=Amat if Amat.size else None, corridors=corridors,
                                                shared_first=shared_first, seed=KMEDOIDS_SEED, append_extremes=True)
                out_costs.append({"region": region, "cutoff": tag, "event": event, "distance": dist, "method": method, "K": K,
                                  "cost": sel["cost"], "cost_with_extremes": selx["cost"], "extremes": len(selx["extremes"]),
                                  "distinct_trajectories": int(len({tuple(r) for r in Cm.round(9)})),
                                  "max_distance": float(Cm.max())})
    # ---------------------------------------------------------------- member sets
    ksets = [("v1", None)]
    ksets += [("v2_first4_uniform", {"method": "first_k", "indices": [0, 1, 2, 3], "weights": [0.25] * 4, "timing": "uniform",
                                    "distance": None, "cost": None, "extremes": []}),
              ("v2_first4_ordered", {"method": "first_k", "indices": [0, 1, 2, 3], "weights": [0.25] * 4, "timing": "ordered",
                                     "distance": None, "cost": None, "extremes": []})]
    for K in KS[1:]:
        for method in METHODS:
            sel = reduction.reduce_members(C["edge_arrival"], K, method, A=Amat if Amat.size else None, corridors=corridors,
                                           shared_first=shared_first, seed=KMEDOIDS_SEED, append_extremes=True)
            sel.update(timing="uniform", distance="edge_arrival")
            ksets.append(("v2_%s_K%d" % (method, K), sel))
    kernels = coverage.Kernels(md["affine_transform"], K_["bridge"].settings_for(T), record["epsg"], shape)
    current_flux = kernels.of_mask(current_native)
    for name, sel in ksets:
        t0 = time.perf_counter()
        if sel is None:
            hz, model, weights, settings_rec = v1_hz, v1_model, None, {"law": "v1 independent per-cell, uniform timing, seed 20261008"}
        else:
            ev = B2.ignition_seconds(fbh_full, sel["indices"], timing=sel["timing"], timing_seed=TIMING_SEED)
            settings = B2.v2_settings(T, member_count=len(sel["indices"]), timing=sel["timing"],
                                      selection={k: sel.get(k) for k in ("method", "distance", "cost", "indices", "weights", "extremes")},
                                      trajectory_identity={"v3_npz_sha256": v3rec["npz_sha256"], "mode": v3rec["trajectory_mode"]})
            _, built = B2.construct_v2(fc, record, cutoff_iso=kit.cutoff_iso(tag), event_id=event, epsg=record["epsg"],
                                       events_full=ev, settings=settings, window=window)
            ids = B2.member_ids("v2:%s:%s" % (tag, name), len(sel["indices"]))
            hz = B2.hazard_arrays(built, ids)
            model = ContactModel.from_arrays(built["events"], built["current"], T, built["remaining_s"], ids=ids, weights=sel["weights"])
            weights = sel["weights"]
            settings_rec = settings["member_selection"]
        build_s = time.perf_counter() - t0
        for m, req0, travel in missions:
            req = req0 if sel is None else B2.rekey_request_k(req0, model.ids, kit.cutoff_iso(tag))
            travel_flags = check.member_reports(graph, hz, req, travel["legs"], travel["destination"]) if travel["status"] == planner.ROUTE else []
            for rule in ({"rule": "all", "k": len(model.ids), "m": len(model.ids)}, A.k_of_m_rule(len(model.ids), 0.9)):
                if rule["rule"] == "k_of_m" and rule["k"] == rule["m"]:
                    dec = dict(dec_all)
                    dec["rule"] = rule
                    dec["reason"] = "K_OF_M_EQUALS_ALL (k = m)"
                    dec["identical_to_all"] = True
                else:
                    dec = decide.decide(graph, hz, req, model, rule=rule, weights=weights)
                if rule["rule"] == "all":
                    dec_all = dec
                relaxed = None
                if rule["rule"] == "all" and name in ("v1", "v2_first4_uniform"):
                    rq = json.loads(json.dumps(req))
                    for d in rq["destinations"]:
                        d["open_intervals"] = [[rq["departure"], rq["horizon"]]]
                    relaxed = planner.sweep_plan(graph, rq, model)
                cov = None
                if dec["verdict"] == decide.CHECKED:
                    spans = check.journey_spans(graph, req, dec["legs"], dec["destination"])
                    nodes = {n["id"]: n for n in graph["nodes"]}
                    issue = K_["independent"]._cell(graph, nodes[req["position"]["node"]])
                    ev_ = coverage.JourneyEvaluator(spans, issue, req["departure"], req)
                    cov, _ = coverage.coverage(ev_, traj_model, kernels=kernels, current_flux=current_flux)
                row = {"region": region, "cutoff": tag, "event": event, "mission": m, "member_set": name,
                       "K_members": len(model.ids), "method": None if sel is None else sel.get("method"),
                       "distance": None if sel is None else sel.get("distance"), "timing": "uniform" if sel is None else sel["timing"],
                       "rule": rule["rule"], "k": rule["k"], "m": rule["m"], "verdict": dec["verdict"], "reason": dec["reason"],
                       "arrival_s": dec["arrival_s"], "decision_wall_s": dec["wall_s"], "build_wall_s": build_s,
                       "planner_calls": dec.get("planner_calls"), "subsets_evaluated": dec.get("subsets_evaluated"),
                       "lazy_iterations": dec.get("lazy_iterations"), "passing_weight": dec.get("passing_weight"),
                       "cvar_alpha": dec.get("cvar_alpha"), "cvar_arrival_s": dec.get("cvar_arrival_s"),
                       "coverage_all_N": cov, "travel_only_arrival_s": travel["arrival"],
                       "travel_only_contact_members": sum(r["contact"] for r in travel_flags),
                       "binding": binding_for(dec, travel, travel_flags, relaxed), "selection": settings_rec,
                       "new_ignitions_per_member": model.new_ignition_counts(),
                       "per_member": [{k: r[k] for k in ("contact", "peak_kw_m2", "dose_kj_m2", "dose_tdu", "passed")} for r in (dec["per_member"] or [])]}
                out_rows.append(row)
                print(json.dumps({k: row[k] for k in ("region", "cutoff", "mission", "member_set", "rule", "verdict", "arrival_s",
                                                       "coverage_all_N", "decision_wall_s")}), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exports", required=True)
    ap.add_argument("--out", default=str(HERE / "data"))
    ap.add_argument("--regions", nargs="*")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    kit.verify_inputs()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, costs = [], []
    host = {"platform": platform.platform(), "python": platform.python_version(), "numpy": np.__version__, "cpu_count": os.cpu_count(),
            "loadavg_start": os.getloadavg(), "note": "host-specific Linux measurement; not comparable with the frozen native-Mac timings"}
    t0 = time.perf_counter()
    for region, tag, event, ms in kit.PANEL:
        if a.regions and region not in a.regions:
            continue
        log = {}
        run_window(region, tag, event, ms, a.exports, rows, costs, log)
    host["loadavg_end"] = os.getloadavg()
    host["total_wall_s"] = time.perf_counter() - t0
    suffix = ("_" + a.tag) if a.tag else ""
    with (out / ("decisions%s.jsonl" % suffix)).open("w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    with (out / ("reduction_costs%s.jsonl" % suffix)).open("w") as f:
        for r in costs:
            f.write(json.dumps(r) + "\n")
    (out / ("host%s.json" % suffix)).write_text(json.dumps(host, indent=1) + "\n")


if __name__ == "__main__":
    main()
