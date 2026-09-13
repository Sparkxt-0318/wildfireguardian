#!/usr/bin/env python
"""G3 / WFG-032: the leak-free 영덕 fold.

의성·안동 2025 and 영덕 2025 are one fire complex (same days, boxes overlapping
128.95–129.1 E). The canonical 영덕 field was simulated by a model trained on the other
five fires INCLUDING 의성·안동, so cells of the same complex may sit in its training set.
This script refits the 영덕 fold with 의성·안동 excluded as well, re-simulates the field on
the SAME canonical canvas (grid, seed, steps, threshold), routes the SAME 458 origins and
the WFG-275 building nodes on it, and grades the routes on the forecast and on the
observed footprint. Everything is written to NEW filenames; the canonical npz and every
committed artifact are untouched and digest-checked.

Rule declared before the run (docs/leakfree_fold.md §2). Laptop only (raw bundle).

    python scripts/run_leakfree_yeongdeok_fold.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.evacuation import future_aware_route, naive_route  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.spread_v2 import data, features, grid as gridmod  # noqa: E402
from wildfireguardian.spread_v2.extent import boundary_contact  # noqa: E402
from wildfireguardian.spread_v2.features import StaticLayers  # noqa: E402
from wildfireguardian.spread_v2.forward_sim import forward_simulate  # noqa: E402
from wildfireguardian.spread_v2.model import IgnitionModelV2, _safe_auc  # noqa: E402
from wildfireguardian.spread_v2.weather import weather_series_from_event  # noqa: E402
from wildfireguardian.buildings import load_buildings  # noqa: E402
from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph  # noqa: E402

from measure_present_perimeter_yeongdeok import CANON, EXPECTED, NPZ as CANON_NPZ, build  # noqa: E402
from regrade_three_way import classify_route, first_seen_grid  # noqa: E402
from run_building_origin_routing import origin_filter  # noqa: E402
from run_multi_region_routing import read_poi_snapshot, snapshot_for  # noqa: E402
from run_real_roads_real_hazard_slope import candidate_origins  # noqa: E402

FIRE, LEAK = "yeongdeok_2025", "uiseong_andong_2025"
OUT_NPZ = REPO / "data/processed/routing_demo_leakfree.npz"
OUT = REPO / "data/processed/leakfree_yeongdeok_fold.json"
DOC = REPO / "docs/leakfree_fold.md"
PROTECTED = [REPO / "data/processed/routing_demo_canonical.npz", REPO / "data/processed/spread_v2_lofo.json",
             REPO / "data/raw/firms_data/fire_manifest.json"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def partition(net, cand, hazard, p_cut, budget, step):
    counts = {"both_safe": 0, "naive_into_FA_safe": 0, "no_safe_route": 0, "other": 0}
    routes = {}
    for n in cand:
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=p_cut, objective="length_m")
        fa = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=budget, p_cut=p_cut, time_step_min=step)
        if nv.reached and nv.enters_hazard and fa.reached and not fa.enters_hazard: b = "naive_into_FA_safe"
        elif nv.reached and nv.enters_hazard and not fa.reached: b = "no_safe_route"
        elif nv.reached and not nv.enters_hazard and fa.reached and not fa.enters_hazard: b = "both_safe"
        else: b = "other"
        counts[b] += 1; routes[n] = (b, nv, fa)
    return counts, routes


def observed(net, routes, fs, t, grid, budget):
    out = {"fire_blind": {}, "forecast_aware": {}}
    for n, (b, nv, fa) in routes.items():
        for arm, r in (("fire_blind", nv), ("forecast_aware", fa)):
            if not r.reached or r.total_time_min > budget:
                out[arm][n] = "not_reached"
            else:
                out[arm][n] = classify_route(net, list(r.route), fs, t, grid)["class_m0"]
    return out


def main() -> int:
    t0 = time.monotonic()
    digests_before = {str(p.relative_to(REPO)): sha(p) for p in PROTECTED}
    canon_doc = json.loads((REPO / "data/processed/canonical_hazard.json").read_text(encoding="utf-8"))
    prm = canon_doc["parameters"]; canvas = canon_doc["canvas"]
    bbox = tuple(canvas["final_bbox_wgs84"]); cell = float(prm["cell_size_m"])

    print("[1/6] dataset ...", flush=True)
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=cell, buffer_m=float(_cfg("grid.feature_buffer_m", 6000.0)))
    n_rows, n_pos = int(len(ds)), int(ds["label"].sum())
    if (n_rows, n_pos) != (canon_doc["dataset"]["n_rows"], canon_doc["dataset"]["n_positives"]):
        print(f"STOP: dataset {n_rows}/{n_pos} != canonical {canon_doc['dataset']}", file=sys.stderr); return 2
    # the overlap that motivates the fold, counted from the raw detections
    det = pd.read_csv(REPO / f"data/raw/firms_data/{LEAK}_detections.csv")
    ybox = data.load_event(FIRE).meta.bbox_wgs84
    loncol = next(c for c in det.columns if c.lower() in ("longitude", "lon")); latcol = next(c for c in det.columns if c.lower() in ("latitude", "lat"))
    inside = det[(det[loncol] >= ybox[0]) & (det[loncol] <= ybox[2]) & (det[latcol] >= ybox[1]) & (det[latcol] <= ybox[3])]
    overlap = {"leak_fire_detections_total": int(len(det)), "inside_yeongdeok_bbox": int(len(inside)),
               "dataset_rows": {f: int((ds["fire_id"] == f).sum()) for f in (FIRE, LEAK)},
               "dataset_positives": {f: int(ds.loc[ds["fire_id"] == f, "label"].sum()) for f in (FIRE, LEAK)}}
    print(f"      {n_rows:,} rows / {n_pos:,} positives; {LEAK} detections inside the 영덕 box: {overlap['inside_yeongdeok_bbox']} of {overlap['leak_fire_detections_total']}", flush=True)

    print("[2/6] fitting canonical (leave-target-out) and leak-free (leave-complex-out) ...", flush=True)
    seed = int(prm["seed"])
    m_canon = IgnitionModelV2(seed=seed).fit(ds[ds["fire_id"] != FIRE])
    m_free = IgnitionModelV2(seed=seed).fit(ds[~ds["fire_id"].isin([FIRE, LEAK])])
    test = ds[ds["fire_id"] == FIRE]
    auc = {"canonical_fold": _safe_auc(test["label"].to_numpy(), m_canon.predict_proba(test)),
           "leakfree_fold": _safe_auc(test["label"].to_numpy(), m_free.predict_proba(test)),
           "training_rows": {"canonical": int((ds["fire_id"] != FIRE).sum()), "leakfree": int((~ds["fire_id"].isin([FIRE, LEAK])).sum())},
           "training_positives": {"canonical": int(ds.loc[ds["fire_id"] != FIRE, "label"].sum()), "leakfree": int(ds.loc[~ds["fire_id"].isin([FIRE, LEAK]), "label"].sum())}}
    print(f"      held-out 영덕 AUC: canonical {auc['canonical_fold']:.4f}  leak-free {auc['leakfree_fold']:.4f}", flush=True)

    print("[3/6] simulating on the canonical canvas ...", flush=True)
    ev = data.load_event(FIRE); ws = weather_series_from_event(ev)
    hg = gridmod.build_grid(bbox, cell_size_m=cell)
    snaps = gridmod.overpass_snapshots(ev, hg, gap_minutes=90.0)
    hstatic = StaticLayers.from_event(ev, hg)
    sim = forward_simulate(m_free, ev, hg, hstatic, snaps[0].cumulative_mask, snaps[0].time, ws,
                           n_steps=int(prm["n_advance_steps"]), step_hours=float(prm["step_hours"]),
                           advance_threshold=float(prm["advance_threshold"]))
    hz_free = HazardSequence.from_forward_sim(sim)
    stack = np.array(hz_free.surfaces, dtype=np.float32)
    zc = np.load(CANON_NPZ)
    assert stack.shape == zc["haz_stack"].shape, (stack.shape, zc["haz_stack"].shape)
    assert np.allclose(zc["grid_extent"], [hg.minx, hg.miny, hg.maxx, hg.maxy, hg.cell_size_m])
    contact = [dict(boundary_contact(stack[i]), slice=i) for i in range(stack.shape[0])]
    cells_free = [int((stack[i] >= 0.5).sum()) for i in range(stack.shape[0])]
    cells_canon = [int((zc["haz_stack"][i] >= 0.5).sum()) for i in range(zc["haz_stack"].shape[0])]
    inter = [int(((stack[i] >= 0.5) & (zc["haz_stack"][i] >= 0.5)).sum()) for i in range(stack.shape[0])]
    union = [int(((stack[i] >= 0.5) | (zc["haz_stack"][i] >= 0.5)).sum()) for i in range(stack.shape[0])]
    np.savez_compressed(OUT_NPZ, grid_extent=zc["grid_extent"], haz_times=hz_free.times_min, haz_stack=stack,
                        obs_times=zc["obs_times"], obs_stack=zc["obs_stack"], ign_xy=zc["ign_xy"])
    print(f"      core cells >=0.5 per slice: leak-free {cells_free}  canonical {cells_canon}", flush=True)

    print("[4/6] routing the 458 canonical origins on both fields ...", flush=True)
    canon, rprm, hz_canon, haz_c, extent, net, snapsfiles = build()
    p_cut, budget, step = float(rprm["p_cut"]), float(rprm["time_budget_min"]), float(rprm["time_step_min"])
    cand_c, _ = candidate_origins(net, hz_canon, haz_c, extent, p_cut)
    cand_f, _ = candidate_origins(net, hz_free, stack, extent, p_cut)
    same_origins = sorted(cand_c) == sorted(cand_f)
    counts_c, routes_c = partition(net, cand_c, hz_canon, p_cut, budget, step)
    if {k: counts_c[k] for k in EXPECTED} != EXPECTED:
        print(f"STOP: canonical partition {counts_c} != {EXPECTED}", file=sys.stderr); return 3
    counts_f, routes_f = partition(net, cand_c, hz_free, p_cut, budget, step)   # SAME origin set, by rule
    fs, obs_t = first_seen_grid(zc)
    obs_c = observed(net, routes_c, fs, obs_t, hz_canon.grid, budget); obs_f = observed(net, routes_f, fs, obs_t, hz_free.grid, budget)
    def tally(o): return {arm: {c: sum(1 for v in o[arm].values() if v == c) for c in ("admissible_all", "indeterminate", "inadmissible_all", "not_reached")} for arm in o}
    fa_only_c = {n for n, (b, _, _) in routes_c.items() if b == "naive_into_FA_safe"}
    fa_only_f = {n for n, (b, _, _) in routes_f.items() if b == "naive_into_FA_safe"}
    print(f"      458 partition: canonical {counts_c}  leak-free {counts_f}; FA-only overlap {len(fa_only_c & fa_only_f)}", flush=True)

    print("[5/6] routing the WFG-275 building nodes on both fields ...", flush=True)
    bld = load_buildings(FIRE, source="juso_main", repo=REPO)
    G = load_snapshot_graph(snapshot_for(FIRE, "walk"))
    bnet, _ = build_walk_network(G, REPO / f"data/raw/firms_data/{FIRE}_dem.tif", sampling_m=60.0, max_abs_slope=0.6, directed=True, apply_slope=True)
    dests, _ = read_poi_snapshot(snapshot_for(FIRE, "shelters"), kind="shelter"); bnet.shelters = {bnet.nearest_node(d.x, d.y) for d in dests}
    snap = []; sd = []
    for i in range(len(bld)):
        nid = bnet.nearest_node(float(bld.xy[i, 0]), float(bld.xy[i, 1])); x, y = bnet.node_xy(nid); snap.append(nid); sd.append(np.hypot(x - bld.xy[i, 0], y - bld.xy[i, 1]))
    sd = np.array(sd); keep_c, _, _ = origin_filter(bld.xy, haz_c, extent, p_cut); keep_f, _, _ = origin_filter(bld.xy, stack, extent, p_cut)
    routable = (sd <= 500.0) & keep_c
    nodes = np.array(snap, dtype=np.int64)[routable]; uniq, counts = np.unique(nodes, return_counts=True); w = dict(zip(uniq.tolist(), counts.tolist()))
    bc_c, br_c = partition(bnet, [int(n) for n in uniq], hz_canon, p_cut, budget, step)
    bc_f, br_f = partition(bnet, [int(n) for n in uniq], hz_free, p_cut, budget, step)
    def bweights(routes): return {k: sum(w[n] for n, (b, _, _) in routes.items() if b == k) for k in ("both_safe", "naive_into_FA_safe", "no_safe_route", "other")}
    bo_c = observed(bnet, br_c, fs, obs_t, hz_canon.grid, budget); bo_f = observed(bnet, br_f, fs, obs_t, hz_free.grid, budget)
    def btally(o): return {arm: {c: sum(w[n] for n, v in o[arm].items() if v == c) for c in ("admissible_all", "indeterminate", "inadmissible_all", "not_reached")} for arm in o}
    print(f"      buildings: canonical {bweights(br_c)}  leak-free {bweights(br_f)}; filtered-out under leak-free field: {int((routable & ~keep_f).sum())}", flush=True)

    print("[6/6] writing ...", flush=True)
    digests_after = {k: sha(REPO / k) for k in digests_before}
    assert digests_before == digests_after, "a protected file changed"
    result = {
        "schema_version": 1, "title": "Leak-free 영덕 fold (의성·안동 excluded from training) — field, 458-origin partition, building partition, observed grading",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip(),
        "config_hash": config_hash(), "rule_doc": "docs/leakfree_fold.md §2 (pre-registered)",
        "protected_digests_unchanged": digests_after,
        "dataset": {"n_rows": n_rows, "n_positives": n_pos, "fires": sorted(ds["fire_id"].unique())},
        "overlap": overlap, "held_out_yeongdeok_auc": auc,
        "field": {"npz": str(OUT_NPZ.relative_to(REPO)), "npz_sha256": sha(OUT_NPZ), "canvas": canvas, "parameters": prm,
                  "cells_ge_0.5_per_slice": {"leakfree": cells_free, "canonical": cells_canon}, "core_iou_per_slice": [round(i / u, 4) if u else None for i, u in zip(inter, union)],
                  "boundary_contact": contact},
        "origins_458": {"same_origin_set_under_leakfree_t0": same_origins, "n": len(cand_c),
                        "partition_canonical": counts_c, "partition_leakfree": counts_f,
                        "fa_only_canonical": sorted(fa_only_c), "fa_only_leakfree": sorted(fa_only_f), "fa_only_overlap": len(fa_only_c & fa_only_f),
                        "observed_canonical": tally(obs_c), "observed_leakfree": tally(obs_f),
                        "fa_only_leakfree_observed_class": {c: sum(1 for n in fa_only_f if obs_f["forecast_aware"][n] == c) for c in ("admissible_all", "indeterminate", "inadmissible_all", "not_reached")},
                        "fa_only_canonical_observed_class": {c: sum(1 for n in fa_only_c if obs_c["forecast_aware"][n] == c) for c in ("admissible_all", "indeterminate", "inadmissible_all", "not_reached")}},
        "buildings": {"n_routable": int(routable.sum()), "n_nodes": int(len(uniq)), "filtered_out_under_leakfree_t0": int((routable & ~keep_f).sum()),
                      "partition_canonical": bweights(br_c), "partition_leakfree": bweights(br_f),
                      "observed_canonical": btally(bo_c), "observed_leakfree": btally(bo_f)},
        "seconds": round(time.monotonic() - t0, 1),
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    o = result["origins_458"]; b = result["buildings"]
    L = ["", f"_Run {result['generated_utc']} at `{result['git_commit'][:7]}`; artifact `{OUT.relative_to(REPO)}`; field `{OUT_NPZ.relative_to(REPO)}`; {result['seconds']:.0f} s. Protected digests unchanged._", "",
         f"- Overlap that motivates the fold: {overlap['inside_yeongdeok_bbox']} of {overlap['leak_fire_detections_total']} 의성·안동 detections lie inside the 영덕 box; training rows drop from {auc['training_rows']['canonical']:,} to {auc['training_rows']['leakfree']:,} (positives {auc['training_positives']['canonical']:,} → {auc['training_positives']['leakfree']:,}).",
         f"- Held-out 영덕 AUC: canonical fold {auc['canonical_fold']:.4f}, leak-free fold {auc['leakfree_fold']:.4f}.",
         f"- Field: core cells (p ≥ 0.5) per slice leak-free {cells_free} vs canonical {cells_canon}; core IoU per slice {result['field']['core_iou_per_slice']}; boundary contact " + ("none" if not any(c['edges_reached'] for c in contact) else str([c['edges_reached'] for c in contact])) + ".",
         f"- 458 origins (same set: {same_origins}): partition canonical {counts_c} → leak-free {counts_f}; forecast-only overlap {o['fa_only_overlap']} of {len(fa_only_c)} / {len(fa_only_f)}.",
         f"- 458 origins graded on the observation, forecast-aware route: canonical {o['observed_canonical']['forecast_aware']} → leak-free {o['observed_leakfree']['forecast_aware']}; of the leak-free forecast-only set {o['fa_only_leakfree_observed_class']} (canonical set {o['fa_only_canonical_observed_class']}).",
         f"- Buildings ({b['n_routable']:,} on {b['n_nodes']:,} nodes; {b['filtered_out_under_leakfree_t0']} would be filtered out by the leak-free t0 field, kept for pairing): partition canonical {b['partition_canonical']} → leak-free {b['partition_leakfree']}; observed forecast-aware canonical {b['observed_canonical']['forecast_aware']} → leak-free {b['observed_leakfree']['forecast_aware']}."]
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
