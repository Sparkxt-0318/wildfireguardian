#!/usr/bin/env python
"""F1 — the frozen-weather field (K-SPREAD Stage 2; docs/auto/briefs/K_SPREAD_STAGE2.md).

The committed 영덕 field is a HINDCAST: ``forward_simulate`` advances each step with the
ERA5 reanalysis AT THAT STEP, which is weather that had not happened at T0
(docs/benchmark/results_v0.1.md §2). F1 is the same model, the same canvas, the same seed
and the same steps, driven instead by the ERA5 values at the LAST TIME AT OR BEFORE T0,
held flat for the whole simulation --- what an operator with no forecast would assume.

⚠ 「last time at or before T0」, NOT 「nearest time to T0」. ``WeatherSeries.at`` picks the
nearest index, which at a step boundary can be a LATER observation; an operator standing at
T0 cannot see it however close it is. ``freeze_at_t0`` below replaces the value arrays with
constants so no lookup can reach past T0 --- the leak this whole correction is about, in
miniature, and the one line where it would come back.

⚠ F1 IS A FLOOR AND NOT AN ESTIMATE of what a real forecast buys. It is the worst honest
assumption. Only F2, on an issued 동네예보, says what a forecaster could have recovered.
docs/forecast_track.md §3 fixes that reading and it is not renegotiated after the numbers.

⚠ NAMING. docs/auto/briefs/K_SPREAD_STAGE2.md is canonical (author's choice, 2026-09-14):
this entrant is **F1**, its F2 is the observed mountain-station field, and the KMA forecast
is **F3** (scripts/run_forecast_track_f3_kma.py). An earlier draft called this E4a.

⚠ NO NEW MODEL IS FITTED. Stage 2 says F1 reuses E3's fitted model rather than training a
second one. No model is persisted anywhere in this repository, so the only way to obtain
E3's is to reproduce its fold deterministically — same training set, same seed. This script
does that and then REFUSES TO CONTINUE unless the reproduction matches the committed
leak-free artifact on training rows, training positives and held-out AUC to full precision.
That turns 「reuse」 into a checked claim instead of an assumption.

Rule declared before the run: docs/forecast_track.md §2. Laptop only (raw bundle).
Every output is a NEW filename; the canonical and leak-free npz are digest-checked.

    python scripts/run_forecast_track_f1.py
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

FIRE, LEAK = "yeongdeok_2025", "uiseong_andong_2025"
OUTDIR = REPO / "data/processed/forecast_track"
OUT_NPZ = OUTDIR / "routing_demo_f1_frozen_t0.npz"
OUT = OUTDIR / "forecast_track_f1.json"
ENTRANT_DIR = REPO / "data/processed/benchmark/entrants/f1_wfg_frozen_t0"
LEAKFREE_JSON = REPO / "data/processed/leakfree_yeongdeok_fold.json"
DOC = REPO / "docs/forecast_track.md"

#: Checked BEFORE any heavy import or fit, so a machine without the bundle is told in one
#: second rather than after the dataset build. data/raw/** is git-ignored (CHARTER §4).
REQUIRED_RAW = (
    f"data/raw/firms_data/{FIRE}_era5.nc",
    f"data/raw/firms_data/{FIRE}_dem.tif",
    f"data/raw/firms_data/{LEAK}_detections.csv",
    "data/raw/firms_data/fire_manifest.json",
)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def preflight() -> int:
    missing = [r for r in REQUIRED_RAW if not (REPO / r).exists()]
    if not missing:
        return 0
    print("F1 (frozen weather at T0) DID NOT RUN.", file=sys.stderr)
    print("  reason: the git-ignored raw bundle is not on this machine.", file=sys.stderr)
    for r in missing:
        print(f"    MISSING {r}", file=sys.stderr)
    print(file=sys.stderr)
    print("  data/raw/** is git-ignored, so a fresh clone NEVER has it (CHARTER §4", file=sys.stderr)
    print("  「Sandbox facts」). F1 needs the ERA5 .nc to freeze, the DEM .tif for the slope", file=sys.stderr)
    print("  walk network, and the detections CSV for the overlap count. Run this on the", file=sys.stderr)
    print("  author's laptop, or set $WFG_FIRMS_DIR to a copy of the bundle.", file=sys.stderr)
    print(file=sys.stderr)
    print("  ⚠ An empty data/raw in a fresh checkout is NOT evidence that the author has no", file=sys.stderr)
    print("    data (see commit 4994f99). It means THIS machine cannot reach it.", file=sys.stderr)
    return 2


def freeze_at_t0(ws, t0):
    """A WeatherSeries whose every lookup returns the values at the last time <= t0.

    Implemented by replacing the VALUE arrays with constants rather than by wrapping
    ``at()``: ``forward_simulate`` reaches the weather only through ``at()``, but a future
    caller might index the arrays directly, and a freeze that only covered one accessor
    would be a leak waiting to be reintroduced. The ``time`` index is left alone so the
    object still describes the window it came from.
    """
    from wildfireguardian.spread_v2.weather import WeatherSeries

    t0 = pd.Timestamp(t0)
    if t0.tzinfo is None:
        t0 = t0.tz_localize("UTC")
    # ⚠ Compared as TIMESTAMPS, never as raw int64. `WeatherSeries.at` does
    #   `self.time.view("int64") - when.value`, which is only correct when the index
    #   resolution is NANOSECONDS: under the pinned pandas 3.0.5 a datetime64[us] or
    #   [s] index makes those ints ~1e3/1e9 times smaller than `Timestamp.value`, every
    #   comparison goes one way, and the lookup silently returns the LAST sample. That
    #   is reported in docs/auto/briefs/HINDCAST_CORRECTION_REPORT.md rather than fixed
    #   here: weather.py feeds every committed field, so changing it could move
    #   registered numbers, which is the author's call and not a build agent's.
    #   F1 must not inherit it, because "the last sample" is exactly a post-T0 leak.
    at_or_before = np.nonzero(np.asarray(pd.DatetimeIndex(ws.time) <= t0))[0]
    if len(at_or_before) == 0:
        raise SystemExit(
            f"STOP: no ERA5 sample at or before T0 ({t0}); the series starts at {ws.time[0]}. "
            "F1 cannot be built without a pre-T0 observation, and the NEAREST sample is "
            "exactly what this entrant may not use."
        )
    i = int(at_or_before[-1])
    fields = ("wind_speed_ms", "wind_toward_deg", "wind_u", "wind_v", "temp_c",
              "rh_pct", "vpd_kpa", "days_since_rain", "precip_24h_mm")
    frozen = {f: np.full(len(ws.time), float(getattr(ws, f)[i])) for f in fields}
    held = {f: float(getattr(ws, f)[i]) for f in fields}
    return WeatherSeries(time=ws.time, **frozen), i, held, str(ws.time[i])


def main() -> int:
    rc = preflight()
    if rc:
        return rc

    t_start = time.monotonic()
    from wildfireguardian.config import config_hash, get as _cfg
    from wildfireguardian.routing.hazard import HazardSequence
    from wildfireguardian.spread_v2 import data, features, grid as gridmod
    from wildfireguardian.spread_v2.extent import boundary_contact
    from wildfireguardian.spread_v2.features import StaticLayers
    from wildfireguardian.spread_v2.forward_sim import forward_simulate
    from wildfireguardian.spread_v2.model import IgnitionModelV2, _safe_auc
    from wildfireguardian.spread_v2.weather import weather_series_from_event
    from wildfireguardian.buildings import load_buildings
    from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph

    # The leak-free fold IS the comparison row, so F1 reuses its helpers verbatim rather
    # than restating them: same partition buckets, same observed grading, same build().
    from run_leakfree_yeongdeok_fold import observed, partition
    from measure_present_perimeter_yeongdeok import CANON, EXPECTED, NPZ as CANON_NPZ, build
    from regrade_three_way import first_seen_grid
    from run_building_origin_routing import origin_filter
    from run_multi_region_routing import read_poi_snapshot, snapshot_for
    from run_real_roads_real_hazard_slope import candidate_origins
    from measure_last_safe_departure import lsd_search

    LEAKFREE_NPZ = REPO / "data/processed/routing_demo_leakfree.npz"
    PROTECTED = [CANON_NPZ, LEAKFREE_NPZ, REPO / "data/raw/firms_data/fire_manifest.json"]
    for q in PROTECTED:
        if not q.exists():
            print(f"STOP: {q.relative_to(REPO)} is missing; F1 reports beside it and will not "
                  "invent the row.", file=sys.stderr)
            return 2
    digests_before = {str(q.relative_to(REPO)): sha(q) for q in PROTECTED}
    OUTDIR.mkdir(parents=True, exist_ok=True)

    canon_doc = json.loads((REPO / "data/processed/canonical_hazard.json").read_text(encoding="utf-8"))
    prm, canvas = canon_doc["parameters"], canon_doc["canvas"]
    bbox = tuple(canvas["final_bbox_wgs84"]); cell = float(prm["cell_size_m"])

    print("[1/7] dataset ...", flush=True)
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=cell,
                                buffer_m=float(_cfg("grid.feature_buffer_m", 6000.0)))
    n_rows, n_pos = int(len(ds)), int(ds["label"].sum())
    if (n_rows, n_pos) != (canon_doc["dataset"]["n_rows"], canon_doc["dataset"]["n_positives"]):
        print(f"STOP: dataset {n_rows}/{n_pos} != canonical {canon_doc['dataset']}", file=sys.stderr)
        return 2

    print("[2/7] reproducing E3's fold (no new model) ...", flush=True)
    seed = int(prm["seed"])
    train = ds[~ds["fire_id"].isin([FIRE, LEAK])]
    m_free = IgnitionModelV2(seed=seed).fit(train)
    test = ds[ds["fire_id"] == FIRE]
    auc_held_out = _safe_auc(test["label"].to_numpy(), m_free.predict_proba(test))

    # Stage 2: 「F1/F2 reuse E3's fitted model; no refit」. Nothing persists that model, so it
    # is reproduced from the same rows and seed and then CHECKED against the committed
    # leak-free artifact. A mismatch means this is a DIFFERENT model and F1 would not be the
    # entrant Stage 2 asked for -- so it stops rather than quietly scoring a second model.
    e3 = json.loads(LEAKFREE_JSON.read_text(encoding="utf-8"))["held_out_yeongdeok_auc"]
    got = {"rows": int(len(train)), "positives": int(train["label"].sum()), "auc": auc_held_out}
    want = {"rows": int(e3["training_rows"]["leakfree"]),
            "positives": int(e3["training_positives"]["leakfree"]),
            "auc": float(e3["leakfree_fold"])}
    if got["rows"] != want["rows"] or got["positives"] != want["positives"] \
       or abs(got["auc"] - want["auc"]) > 1e-12:
        print(f"STOP: this is not E3's model.\n  reproduced {got}\n  committed  {want}\n"
              f"  ({LEAKFREE_JSON.relative_to(REPO)}). Stage 2 requires F1 to reuse E3's fit;\n"
              "  scoring a different model under the name F1 would make the leaderboard row a\n"
              "  comparison of two things at once.", file=sys.stderr)
        return 2
    print(f"      reproduced E3 exactly: {got['rows']:,} rows / {got['positives']:,} positives, "
          f"held-out 영덕 AUC {auc_held_out:.16f} == committed {want['auc']:.16f}", flush=True)

    print("[3/7] freezing the weather at T0 and simulating ...", flush=True)
    ev = data.load_event(FIRE)
    ws = weather_series_from_event(ev)
    if ws is None:
        print(f"STOP: no ERA5 series for {FIRE}; F1 is defined by freezing it.", file=sys.stderr)
        return 2
    hg = gridmod.build_grid(bbox, cell_size_m=cell)
    snaps = gridmod.overpass_snapshots(ev, hg, gap_minutes=90.0)
    t0 = pd.Timestamp(snaps[0].time)
    ws_frozen, i_frozen, held, t_frozen = freeze_at_t0(ws, t0)
    # The whole entrant rests on this: nothing after T0 may enter. Assert it rather than
    # trust it, because a silent off-by-one here reproduces the exact defect being fixed.
    assert pd.Timestamp(ws.time[i_frozen]) <= (t0.tz_localize("UTC") if t0.tzinfo is None else t0), \
        "the frozen sample is AFTER T0"
    probe = ws_frozen.at(t0 + pd.Timedelta(hours=12))
    assert all(abs(probe[k] - held[k]) < 1e-9 for k in held), "the freeze leaks at +12 h"
    print(f"      T0={t0}  frozen sample={t_frozen} (index {i_frozen}); "
          f"wind {held['wind_speed_ms']:.2f} m/s toward {held['wind_toward_deg']:.0f}°, "
          f"VPD {held['vpd_kpa']:.3f} kPa", flush=True)

    hstatic = StaticLayers.from_event(ev, hg)
    sim = forward_simulate(m_free, ev, hg, hstatic, snaps[0].cumulative_mask, snaps[0].time,
                           ws_frozen, n_steps=int(prm["n_advance_steps"]),
                           step_hours=float(prm["step_hours"]),
                           advance_threshold=float(prm["advance_threshold"]))
    hz_f1 = HazardSequence.from_forward_sim(sim)
    stack = np.array(hz_f1.surfaces, dtype=np.float32)
    zc = np.load(CANON_NPZ); zl = np.load(LEAKFREE_NPZ)
    assert stack.shape == zc["haz_stack"].shape, (stack.shape, zc["haz_stack"].shape)
    assert np.allclose(zc["grid_extent"], [hg.minx, hg.miny, hg.maxx, hg.maxy, hg.cell_size_m])

    def cells(a): return [int((a[i] >= 0.5).sum()) for i in range(a.shape[0])]
    def iou(a, b):
        return [round(float(((a[i] >= 0.5) & (b[i] >= 0.5)).sum()) /
                      float(((a[i] >= 0.5) | (b[i] >= 0.5)).sum()), 4)
                if ((a[i] >= 0.5) | (b[i] >= 0.5)).sum() else None for i in range(a.shape[0])]
    np.savez_compressed(OUT_NPZ, grid_extent=zc["grid_extent"], haz_times=hz_f1.times_min,
                        haz_stack=stack, obs_times=zc["obs_times"], obs_stack=zc["obs_stack"],
                        ign_xy=zc["ign_xy"])
    field = {
        "npz": str(OUT_NPZ.relative_to(REPO)), "npz_sha256": sha(OUT_NPZ),
        "canvas": canvas, "parameters": prm,
        "frozen_weather": {"t0": str(t0), "sample_time": t_frozen, "sample_index": i_frozen,
                           "rule": "last ERA5 time at or before T0, held for every step",
                           "values": held},
        "cells_ge_0.5_per_slice": {"f1_frozen": cells(stack), "canonical": cells(zc["haz_stack"]),
                                   "leakfree": cells(zl["haz_stack"])},
        "core_iou_vs_canonical": iou(stack, zc["haz_stack"]),
        "core_iou_vs_leakfree": iou(stack, zl["haz_stack"]),
        "boundary_contact": [dict(boundary_contact(stack[i]), slice=i) for i in range(stack.shape[0])],
        "held_out_yeongdeok_auc_same_fit": auc_held_out,
    }
    print(f"      core cells >=0.5: F1 {field['cells_ge_0.5_per_slice']['f1_frozen']}  "
          f"leak-free {field['cells_ge_0.5_per_slice']['leakfree']}  "
          f"canonical {field['cells_ge_0.5_per_slice']['canonical']}", flush=True)

    result = {
        "schema_version": 1,
        "title": "F1 frozen-weather-at-T0 field (forecast track) — field, 458-origin partition, "
                 "building partition, observed grading, 5-hour rule, NH-057 split",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "config_hash": config_hash(), "rule_doc": "docs/forecast_track.md §2 (pre-registered); naming per docs/auto/briefs/K_SPREAD_STAGE2.md",
        "entrant": "F1", "track": "forecast",
        "dataset": {"n_rows": n_rows, "n_positives": n_pos},
        "field": field,
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print("[4/7] writing the E4a entrant bundle (forecast track) ...", flush=True)
    ENTRANT_DIR.mkdir(parents=True, exist_ok=True)
    ev_npz = ENTRANT_DIR / f"{FIRE}.npz"
    # ⚠ The ENTRANT npz uses the scorer's key names, which are NOT the field npz's.
    # scripts/benchmark/score_kspread.py reads e["stack"] / e["times_min"] / e["grid_extent"]
    # (see the committed e0_persistence and e3_wfg_canonical bundles, which carry exactly
    # those three). The field npz beside it keeps haz_stack / haz_times because that is the
    # routing_demo_*.npz contract. Writing the field's names into an entrant bundle is what
    # made the first F1 score run die with KeyError: 'stack is not a file in the archive',
    # after the field had already taken 36 minutes to build.
    np.savez_compressed(ev_npz, grid_extent=zc["grid_extent"], times_min=hz_f1.times_min,
                        stack=stack)
    (ENTRANT_DIR / "entrant.json").write_text(json.dumps({
        "id": "f1_wfg_frozen_t0", "protocol_entrant": "F1",
        "name": "F1 WFG frozen weather at T0 (E3's fold, reproduced and checked)",
        "protocol_version": "v0.1", "track": "forecast", "resolution_m": float(cell),
        "inputs_used": ["FIRMS cumulative detections at T0", "SRTM/5 m DEM", "land cover",
                        "ERA5 at the last time AT OR BEFORE T0, held flat for every step"],
        "track_reason": "No input is an observation after T0. The weather is frozen at the last "
                        "sample at or before T0, so protocol §3's hindcast trigger does not fire. "
                        "⚠ This is the WORST honest assumption (no forecast at all), so it is a "
                        "FLOOR on what a forecast-driven field would score, not an estimate of "
                        "one — docs/forecast_track.md §3.",
        "what_it_is": "E3's own fitted model (reproduced from the same rows and seed, and "
                      "checked against data/processed/leakfree_yeongdeok_fold.json), driven by "
                      "frozen T0 weather instead of post-T0 reanalysis",
        "provenance": {"source": str(OUT_NPZ.relative_to(REPO)), "array": "haz_stack",
                       "source_sha256": sha(OUT_NPZ),
                       "fold_artifact": str(OUT.relative_to(REPO)),
                       "fitted_by": "scripts/run_forecast_track_f1.py"},
        "events": {FIRE: {"npz": str(ev_npz.relative_to(REPO)), "sha256": sha(ev_npz)}},
        "generated_utc": result["generated_utc"], "git_commit": result["git_commit"],
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"      {ENTRANT_DIR.relative_to(REPO)}  — score it with:", flush=True)
    print(f"      python scripts/benchmark/score_kspread.py --entrant {ENTRANT_DIR.relative_to(REPO)}", flush=True)

    print("[5/7] routing the 458 canonical origins on all three fields ...", flush=True)
    canon, rprm, hz_canon, haz_c, extent, net, _ = build()
    p_cut, budget, step = float(rprm["p_cut"]), float(rprm["time_budget_min"]), float(rprm["time_step_min"])
    cand_c, _ = candidate_origins(net, hz_canon, haz_c, extent, p_cut)
    counts_c, routes_c = partition(net, cand_c, hz_canon, p_cut, budget, step)
    if {k: counts_c[k] for k in EXPECTED} != EXPECTED:
        print(f"STOP: canonical partition {counts_c} != {EXPECTED}", file=sys.stderr)
        return 3
    hz_leak = HazardSequence(grid=hz_canon.grid, times_min=np.asarray(zl["haz_times"], float),
                             surfaces=[zl["haz_stack"][i] for i in range(zl["haz_stack"].shape[0])])
    counts_l, routes_l = partition(net, cand_c, hz_leak, p_cut, budget, step)
    counts_f, routes_f = partition(net, cand_c, hz_f1, p_cut, budget, step)  # SAME origin set, by rule
    fs, obs_t = first_seen_grid(zc)
    obs_c = observed(net, routes_c, fs, obs_t, hz_canon.grid, budget)
    obs_l = observed(net, routes_l, fs, obs_t, hz_leak.grid, budget)
    obs_f = observed(net, routes_f, fs, obs_t, hz_f1.grid, budget)

    def tal(o):
        return {arm: {c: sum(1 for v in o[arm].values() if v == c)
                      for c in ("admissible_all", "indeterminate", "inadmissible_all", "not_reached")}
                for arm in o}

    def fa_only(r): return {n for n, (b, _, _) in r.items() if b == "naive_into_FA_safe"}
    fo_c, fo_l, fo_f = fa_only(routes_c), fa_only(routes_l), fa_only(routes_f)
    result["origins_458"] = {
        "n": len(cand_c),
        "partition_canonical": counts_c, "partition_leakfree": counts_l, "partition_f1_frozen": counts_f,
        "fa_only_counts": {"canonical": len(fo_c), "leakfree": len(fo_l), "f1_frozen": len(fo_f)},
        "fa_only_overlap_f1_vs_leakfree": len(fo_f & fo_l),
        "fa_only_overlap_f1_vs_canonical": len(fo_f & fo_c),
        "fa_only_f1_frozen": sorted(fo_f),
        "observed_canonical": tal(obs_c), "observed_leakfree": tal(obs_l), "observed_f1_frozen": tal(obs_f),
        "fa_only_f1_observed_class": {c: sum(1 for n in fo_f if obs_f["forecast_aware"][n] == c)
                                      for c in ("admissible_all", "indeterminate", "inadmissible_all", "not_reached")},
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"      458 partition: canonical {counts_c}  leak-free {counts_l}  F1 {counts_f}", flush=True)

    print("[6/7] routing the 주건물 nodes and the 5-hour rule ...", flush=True)
    bld = load_buildings(FIRE, source="juso_main", repo=REPO)
    G = load_snapshot_graph(snapshot_for(FIRE, "walk"))
    bnet, _ = build_walk_network(G, REPO / f"data/raw/firms_data/{FIRE}_dem.tif", sampling_m=60.0,
                                 max_abs_slope=0.6, directed=True, apply_slope=True)
    dests, _ = read_poi_snapshot(snapshot_for(FIRE, "shelters"), kind="shelter")
    bnet.shelters = {bnet.nearest_node(d.x, d.y) for d in dests}
    snap, sd = [], []
    for i in range(len(bld)):
        nid = bnet.nearest_node(float(bld.xy[i, 0]), float(bld.xy[i, 1]))
        x, y = bnet.node_xy(nid); snap.append(nid)
        sd.append(float(np.hypot(x - bld.xy[i, 0], y - bld.xy[i, 1])))
    sd = np.array(sd)
    keep_c, _, _ = origin_filter(bld.xy, haz_c, extent, p_cut)
    keep_f, _, _ = origin_filter(bld.xy, stack, extent, p_cut)
    routable = (sd <= 500.0) & keep_c          # canonical routable set, so the rows are paired
    nodes = np.array(snap, dtype=np.int64)[routable]
    uniq, cnt = np.unique(nodes, return_counts=True)
    w = dict(zip(uniq.tolist(), cnt.tolist()))
    bc_c, br_c = partition(bnet, [int(n) for n in uniq], hz_canon, p_cut, budget, step)
    bc_l, br_l = partition(bnet, [int(n) for n in uniq], hz_leak, p_cut, budget, step)
    bc_f, br_f = partition(bnet, [int(n) for n in uniq], hz_f1, p_cut, budget, step)

    def bw(r): return {k: sum(w[n] for n, (b, _, _) in r.items() if b == k)
                       for k in ("both_safe", "naive_into_FA_safe", "no_safe_route", "other")}

    def bt(o): return {arm: {c: sum(w[n] for n, v in o[arm].items() if v == c)
                             for c in ("admissible_all", "indeterminate", "inadmissible_all", "not_reached")}
                       for arm in o}
    bo_c = observed(bnet, br_c, fs, obs_t, hz_canon.grid, budget)
    bo_l = observed(bnet, br_l, fs, obs_t, hz_leak.grid, budget)
    bo_f = observed(bnet, br_f, fs, obs_t, hz_f1.grid, budget)

    # 5-hour rule: docs/last_safe_departure.md's own cuts, building-weighted.
    def lsd_buckets(hazard):
        b = {"never": 0, "closes_before_5h": 0, "closes_after_5h": 0, "censored": 0}
        for n in uniq:
            v = lsd_search(bnet, int(n), hazard)
            k = ("never" if v < 0 else "censored" if v >= 600.0
                 else "closes_before_5h" if v < 300.0 else "closes_after_5h")
            b[k] += w[int(n)]
        return b
    result["buildings"] = {
        "n_routable": int(routable.sum()), "n_nodes": int(len(uniq)),
        "filtered_out_under_f1_t0": int((routable & ~keep_f).sum()),
        "partition_canonical": bw(br_c), "partition_leakfree": bw(br_l), "partition_f1_frozen": bw(br_f),
        "observed_canonical": bt(bo_c), "observed_leakfree": bt(bo_l), "observed_f1_frozen": bt(bo_f),
        "last_safe_departure_5h_rule": {
            "cuts": "never / closes_before_5h (<300 min) / closes_after_5h / censored (>=600)",
            "canonical": lsd_buckets(hz_canon), "leakfree": lsd_buckets(hz_leak),
            "f1_frozen": lsd_buckets(hz_f1)},
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"      buildings: canonical {bw(br_c)}  leak-free {bw(br_l)}  F1 {bw(br_f)}", flush=True)

    print("[7/7] the NH-057 four-way rescue split on the F1 field ...", flush=True)
    # Mirrors run_rescue_routing_real_hazard.main() exactly, with one difference: the
    # scenario is built on the F1 npz instead of the canonical one. LAST ON PURPOSE --
    # it is the heaviest stage and the only one that materialises OSM snapshots, and
    # every earlier result is already on disk before it starts.
    import shutil, tempfile
    tmp = Path(tempfile.mkdtemp(prefix="wfg-f1-snap-"))
    try:
        from wildfireguardian.routing.rescue import RescueConfig
        from wildfireguardian.routing.rescue_demo import run_pipeline
        from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE
        from run_rescue_routing_full import materialise_snapshots
        from run_rescue_routing_real_hazard import build_scenario

        materialise_snapshots(tmp / FIRE)
        rcfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp), scan_stride=REAL_OSM_SCAN_STRIDE)
        sc = build_scenario(rcfg, npz=OUT_NPZ)
        res = run_pipeline(sc, rcfg)
        pe = res.responder_exposure
        result["nh057_four_way_split_f1"] = {
            "ran": True,
            "n_origins": len(sc.origins),
            "four_way_counts": {str(k): int(v) for k, v in res.four_way_counts.items()},
            "n_need_rescue": int(pe["n_need_rescue"]),
            "n_unreachable": int(pe["n_unreachable"]),
            "note": "The same pipeline docs/rescue_routing_real_hazard.md §3 reports on the "
                    "CANONICAL (hindcast) field, recomputed on the F1 field. Origins are "
                    "sampled walk-network candidates and not households, and the walk timing "
                    "is flat: every caveat in that page's §4 applies here unchanged.",
        }
        print(f"      four-way on F1: {res.four_way_counts}", flush=True)
    except Exception as exc:   # noqa: BLE001 - reported, never silently dropped
        result["nh057_four_way_split_f1"] = {
            "ran": False, "error": f"{type(exc).__name__}: {exc}",
            "note": "The earlier stages are already written to this artifact. This split runs "
                    "LAST on purpose so a failure here costs nothing that came before it.",
        }
        print(f"      NH-057 split did NOT run: {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    digests_after = {k: sha(REPO / k) for k in digests_before}
    assert digests_before == digests_after, "a protected file changed"
    result["protected_digests_unchanged"] = digests_after
    result["seconds"] = round(time.monotonic() - t_start, 1)
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(REPO)} and {OUT_NPZ.relative_to(REPO)} in {result['seconds']:.0f} s")
    print(f"Now fill {DOC.relative_to(REPO)} §4 from this artifact, and score F1 on the benchmark.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
