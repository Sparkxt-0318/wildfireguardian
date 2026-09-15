#!/usr/bin/env python
"""WFG-073 / paper gap G6: does the canonical 영덕 partition depend on refuge PROVENANCE?

Every refuge in this project's results is an OpenStreetMap point. The 행정안전부
주소정보누리집 designated subset for 영덕군 has been committed since 2026-09-04 and has
never been routed against. This runs the SAME 458 origins on the SAME canonical hazard
field with the SAME parameters against four refuge sets and reports the three-bucket
partition and the observed three-way grading for each.

    THE RULE IS PRE-REGISTERED in docs/refuge_provenance.md §2 and was committed BEFORE
    this script was run. Nothing here chooses a verdict after the answer.

    The hard reproduction gate (§2.4): arm `osm` must re-derive 458 origins and
    414 / 42 / 2 from 50 POIs on 46 shelter nodes, or the run STOPS and the other arms
    are not reported as comparable. Nothing is tuned to make it reproduce.

Writes data/processed/refuge_provenance_yeongdeok.json and appends §3 to the doc.
Touches no committed artifact; digest-checks the two that matter before and after.

    python scripts/run_refuge_provenance.py
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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.config import get as _cfg  # noqa: E402
from wildfireguardian.routing.evacuation import future_aware_route, naive_route  # noqa: E402

from measure_present_perimeter_yeongdeok import (  # noqa: E402
    EXPECTED, EXPECTED_ORIGINS, NPZ, build, sha256,
)
from regrade_three_way import MISS, classify_route, first_seen_grid  # noqa: E402
from run_real_roads_real_hazard_slope import candidate_origins  # noqa: E402
from run_yeongdeok_canonical_routing import REGION, refuge_destinations  # noqa: E402

OUT = REPO / "data/processed/refuge_provenance_yeongdeok.json"
DOC = REPO / "docs/refuge_provenance.md"
JUSO_DIR = REPO / "data/processed/external/juso_yeongdeok"

ARMS = ("osm", "designated", "union", "designated_plus_tsunami")
ARM_LABEL = {"osm": "osm (committed)", "designated": "designated (primary)",
             "union": "union", "designated_plus_tsunami": "designated_plus_tsunami (sensitivity)"}

#: §2.4 — the committed values arm `osm` must reproduce exactly.
EXPECTED_OSM_POIS = 50
EXPECTED_OSM_SHELTER_NODES = 46

#: Committed artifacts this run must not move.
GUARDED = ("data/processed/real_roads_real_hazard_canonical.json",
           "data/processed/routing_demo_canonical.npz")

CLASSES = ["admissible_all", "indeterminate", "inadmissible_all", "unsupported", "not_reached"]


def digests() -> dict:
    return {rel: sha256(REPO / rel) for rel in GUARDED}


def run_arm(which, net, hazard, cand, prm, fs, obs_t, walk_bbox):
    """One refuge set: partition the 458 origins, then grade both routes observed."""
    dests, n_pois, meta = refuge_destinations(which, walk_bbox)
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    p_cut = float(prm["p_cut"])
    budget = float(prm["time_budget_min"])
    step = float(prm["time_step_min"])

    counts = {"both_safe": 0, "naive_into_FA_safe": 0, "no_safe_route": 0, "other": 0}
    graded = {"fire_blind": {f"m{m}": {c: 0 for c in CLASSES} for m in MISS},
              "forecast_aware": {f"m{m}": {c: 0 for c in CLASSES} for m in MISS}}
    fa_only_graded = {f"m{m}": {c: 0 for c in CLASSES} for m in MISS}
    rows = []
    t0 = time.monotonic()
    for i, n in enumerate(cand):
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=p_cut, objective="length_m")
        fa = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=budget,
                                p_cut=p_cut, time_step_min=step)
        if nv.reached and nv.enters_hazard and fa.reached and not fa.enters_hazard:
            b = "naive_into_FA_safe"
        elif nv.reached and nv.enters_hazard and not fa.reached:
            b = "no_safe_route"
        elif nv.reached and not nv.enters_hazard and fa.reached and not fa.enters_hazard:
            b = "both_safe"
        else:
            b = "other"
        counts[b] += 1
        row = {"origin": int(n), "bucket": b}
        for arm_key, r in (("fire_blind", nv), ("forecast_aware", fa)):
            if r is None or not r.reached or r.total_time_min > budget:
                cls = {f"class_m{m}": "not_reached" for m in MISS}
            else:
                cls = classify_route(net, list(r.route), fs, obs_t, hazard.grid)
            row[arm_key] = {f"m{m}": cls[f"class_m{m}"] for m in MISS}
            for m in MISS:
                graded[arm_key][f"m{m}"][cls[f"class_m{m}"]] += 1
        if b == "naive_into_FA_safe":
            for m in MISS:
                fa_only_graded[f"m{m}"][row["forecast_aware"][f"m{m}"]] += 1
        rows.append(row)
        if (i + 1) % 100 == 0:
            print(f"    [{i + 1}/{len(cand)}] {time.monotonic() - t0:.0f}s", flush=True)
    return {"arm": which, "n_origins": len(cand), "n_refuge_pois": n_pois,
            "n_shelter_nodes": len(net.shelters), "counts": counts,
            "refuge_provenance": meta, "observed_grading": graded,
            "observed_grading_forecast_only_bucket": fa_only_graded,
            "shelter_nodes": sorted(int(v) for v in net.shelters),
            "per_origin": rows}


def main() -> int:
    before = digests()
    print("guarded artifacts:")
    for k, v in before.items():
        print(f"  {v[:16]}...  {k}")

    canon, prm, hazard, haz, extent, net, snaps = build()
    walk_bbox = (_cfg("bbox.multi_region_walk_bbox", {}) or {})[REGION]
    z = np.load(NPZ)
    fs, obs_t = first_seen_grid(z)
    cand, _ign = candidate_origins(net, hazard, haz, extent, float(prm["p_cut"]))
    print(f"\norigins: {len(cand)} (expected {EXPECTED_ORIGINS})")
    if len(cand) != EXPECTED_ORIGINS:
        print(f"STOP: origin count {len(cand)} != {EXPECTED_ORIGINS}", file=sys.stderr)
        return 3

    # ---- every layer's feature count, used or not (§2.1) -------------------
    layer_census = {}
    for p in sorted(JUSO_DIR.glob("*.geojson")):
        raw = json.loads(p.read_text(encoding="utf-8"))
        layer_census[p.stem] = len(raw.get("features", []))

    results = {}
    for which in ARMS:
        print(f"\narm {which}:")
        results[which] = run_arm(which, net, hazard, cand, prm, fs, obs_t, walk_bbox)
        r = results[which]
        print(f"  {r['n_refuge_pois']} POIs -> {r['n_shelter_nodes']} nodes   "
              f"both_safe={r['counts']['both_safe']}  "
              f"FA_only={r['counts']['naive_into_FA_safe']}  "
              f"no_safe={r['counts']['no_safe_route']}  other={r['counts']['other']}")
        if which == "osm":
            got = {k: r["counts"][k] for k in EXPECTED}
            ok = (got == EXPECTED and r["n_refuge_pois"] == EXPECTED_OSM_POIS
                  and r["n_shelter_nodes"] == EXPECTED_OSM_SHELTER_NODES)
            if not ok:
                print(f"\nSTOP (§2.4 reproduction gate FAILED): got {got}, "
                      f"{r['n_refuge_pois']} POIs on {r['n_shelter_nodes']} nodes; "
                      f"expected {EXPECTED}, {EXPECTED_OSM_POIS} POIs on "
                      f"{EXPECTED_OSM_SHELTER_NODES} nodes. The other arms are NOT "
                      f"comparable and are not reported.", file=sys.stderr)
                OUT.with_suffix(".FAILED.json").write_text(
                    json.dumps({"reproduction_gate": "FAILED", "got": r["counts"],
                                "expected": EXPECTED,
                                "n_refuge_pois": r["n_refuge_pois"],
                                "n_shelter_nodes": r["n_shelter_nodes"]},
                               indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
                return 4
            print("  §2.4 reproduction gate: PASS")

    # ---- overlap (§2.6) ----------------------------------------------------
    osm_nodes = set(results["osm"]["shelter_nodes"])
    osm_dests, _n, _m = refuge_destinations("osm", walk_bbox)
    osm_xy = np.array([[d.x, d.y] for d in osm_dests], float)
    overlap = {}
    for which in ("designated", "designated_plus_tsunami"):
        desig, _n2, meta = refuge_destinations(which, walk_bbox)
        desig = [d for d in desig if d.source.startswith("juso:")]
        same_node, dists = 0, []
        for d in desig:
            node = net.nearest_node(d.x, d.y)
            if int(node) in osm_nodes:
                same_node += 1
            dists.append(float(np.min(np.hypot(osm_xy[:, 0] - d.x, osm_xy[:, 1] - d.y))))
        dists = np.array(dists, float)
        overlap[which] = {
            "n_designated_points_in_walk_box": len(desig),
            "n_snapping_to_a_node_already_in_the_osm_shelter_set": same_node,
            "share_snapping_to_an_osm_shelter_node": (same_node / len(desig)) if desig else None,
            "distance_to_nearest_osm_refuge_poi_m": {
                "min": float(dists.min()), "median": float(np.median(dists)),
                "mean": float(dists.mean()), "max": float(dists.max()),
                "within_100m": int((dists <= 100).sum()),
                "within_250m": int((dists <= 250).sum()),
                "within_500m": int((dists <= 500).sum()),
            } if desig else None,
        }

    # ---- the reading rule (§2.6), applied mechanically ---------------------
    o, d = results["osm"]["counts"], results["designated"]["counts"]
    d_fa = abs(d["naive_into_FA_safe"] - o["naive_into_FA_safe"])
    d_ns = abs(d["no_safe_route"] - o["no_safe_route"])
    thr_fa, thr_ns = o["naive_into_FA_safe"] / 3.0, o["no_safe_route"] / 3.0
    depends = (d_fa > thr_fa) or (d_ns > thr_ns)
    verdict = ("the partition depends on refuge provenance" if depends
               else "the absolute rates are robust to refuge provenance")
    reading = {"delta_naive_into_FA_safe": d_fa, "threshold_naive_into_FA_safe": thr_fa,
               "delta_no_safe_route": d_ns, "threshold_no_safe_route": thr_ns,
               "verdict": verdict, "rule": "docs/refuge_provenance.md §2.6 (pre-registered)"}

    doc = {
        "schema_version": 1,
        "title": "WFG-073 / paper gap G6: refuge provenance — OSM refuges versus 행정안전부 designated sites",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                     capture_output=True, text=True).stdout.strip(),
        "rule_doc": "docs/refuge_provenance.md §2 (pre-registered and committed before this ran)",
        "inputs": {"npz": str(NPZ.relative_to(REPO)), "npz_sha256": sha256(NPZ),
                   **{k: str(v.relative_to(REPO)) for k, v in snaps.items()},
                   "juso_dir": str(JUSO_DIR.relative_to(REPO)),
                   "walk_bbox_wgs84": [float(v) for v in walk_bbox],
                   "obs_times_min": [float(v) for v in obs_t]},
        "juso_layer_census_features": layer_census,
        "parameters": {k: prm[k] for k in ("slope_sampling_m", "max_abs_slope", "p_cut",
                                           "time_budget_min", "time_step_min",
                                           "origin_scan_stride", "routing_objective")},
        "reproduction_gate": {"status": "PASS", "expected": EXPECTED,
                              "expected_n_refuge_pois": EXPECTED_OSM_POIS,
                              "expected_n_shelter_nodes": EXPECTED_OSM_SHELTER_NODES},
        "arms": {k: {kk: vv for kk, vv in v.items() if kk != "per_origin"}
                 for k, v in results.items()},
        "overlap": overlap,
        "reading_rule": reading,
        "per_origin": {k: v["per_origin"] for k, v in results.items()},
        "caveats": [
            "bears on the ABSOLUTE 영덕 rates only; the paired fire-blind vs forecast-aware "
            "contrast uses the same refuge set in both arms and is unaffected by construction",
            "the 사물주소 categories are earthquake, tsunami and heat — none is a designated "
            "wildfire refuge; openness, staffing and capacity are unknown (NH-012 b)",
            "designated points are CLIPPED to the canonical walk box before snapping; the two "
            "sets are never differenced as they stand (docs/juso_yeongdeok.md)",
            "observed grading is the pre-registered rule of docs/regrade_three_way.md §2-§3, "
            "with its assumptions A1-A6; no count here is a safety rate",
        ],
    }
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    after = digests()
    moved = [k for k in before if before[k] != after[k]]
    if moved:
        print(f"\nSTOP (exit 4): guarded artifact(s) changed: {moved}", file=sys.stderr)
        return 4

    # ---- §3 of the doc -----------------------------------------------------
    L = ["", f"_Run {doc['generated_utc']} at `{doc['git_commit'][:7]}`; artifact "
             f"`{OUT.relative_to(REPO)}`; {len(cand)} origins in every arm; "
             f"reproduction gate (§2.4) **PASSED**._", "",
         "### 3.1 The four arms", "",
         "| arm | refuge POIs | snapped nodes | both_safe | naive_into_FA_safe | no_safe_route | other |",
         "|---|---:|---:|---:|---:|---:|---:|"]
    for a in ARMS:
        r = results[a]
        c = r["counts"]
        L.append(f"| {ARM_LABEL[a]} | {r['n_refuge_pois']} | {r['n_shelter_nodes']} | "
                 f"{c['both_safe']} | {c['naive_into_FA_safe']} | {c['no_safe_route']} | {c['other']} |")
    L += ["", "### 3.2 Extent: what the clip to the canonical walk box dropped (§2.2)", "",
          "| layer | features | inside walk box | dropped |", "|---|---:|---:|---:|"]
    for stem, st in results["designated_plus_tsunami"]["refuge_provenance"]["designated_layers"].items():
        L.append(f"| `{stem}` | {st['features']} | {st['inside_walk_box']} | "
                 f"{st['dropped_outside_walk_box']} |")
    L += ["", "Every layer in the folder, used or not:", "",
          "| layer | features | used as a refuge candidate? |", "|---|---:|---|"]
    used = {"samul_eqout_point": "yes — primary", "samul_coolingcen_point": "yes — primary",
            "samul_eqwav_point": "sensitivity arm only", "minwon_agencies": "no — depots (WFG-074)",
            "samul_firehydr_point": "no", "samul_busst_point": "no",
            "samul_lifesav_point": "no — empty", "samul_emerwat_point": "no — empty"}
    for stem, n in sorted(layer_census.items()):
        L.append(f"| `{stem}` | {n} | {used.get(stem, 'no')} |")

    L += ["", "### 3.3 Observed three-way grading (docs/regrade_three_way.md §2–§3, A1–A6)", "",
          "| arm | route | m | admissible for all | indeterminate | inadmissible for all | unsupported | not reached |",
          "|---|---|---|---:|---:|---:|---:|---:|"]
    for a in ARMS:
        for rk, rl in (("fire_blind", "fire-blind"), ("forecast_aware", "forecast-aware")):
            for m in MISS:
                c = results[a]["observed_grading"][rk][f"m{m}"]
                L.append(f"| {ARM_LABEL[a]} | {rl} | {m} | {c['admissible_all']} | "
                         f"{c['indeterminate']} | {c['inadmissible_all']} | "
                         f"{c['unsupported']} | {c['not_reached']} |")
    L += ["", "The forecast-only bucket (`naive_into_FA_safe`) of each arm, forecast-aware route:", ""]
    for a in ARMS:
        parts = []
        for m in MISS:
            c = results[a]["observed_grading_forecast_only_bucket"][f"m{m}"]
            parts.append(f"m={m}: adm {c['admissible_all']} / indet {c['indeterminate']} / "
                         f"inadm {c['inadmissible_all']}")
        L.append(f"- **{ARM_LABEL[a]}** (n = {results[a]['counts']['naive_into_FA_safe']}): "
                 + "; ".join(parts))

    L += ["", "### 3.4 Overlap between the designated sites and the OSM refuges (§2.6)", ""]
    for which, ov in overlap.items():
        dd = ov["distance_to_nearest_osm_refuge_poi_m"]
        L.append(f"- **{which}**: {ov['n_designated_points_in_walk_box']} designated points "
                 f"inside the walk box; "
                 f"**{ov['n_snapping_to_a_node_already_in_the_osm_shelter_set']}** of them snap "
                 f"to a walk-graph node that is already in the OSM arm's shelter-node set "
                 f"({ov['share_snapping_to_an_osm_shelter_node'] * 100:.1f} %). "
                 f"Distance to the nearest OSM refuge POI: min {dd['min']:.0f} m, "
                 f"median {dd['median']:.0f} m, max {dd['max']:.0f} m; "
                 f"{dd['within_100m']} within 100 m, {dd['within_250m']} within 250 m, "
                 f"{dd['within_500m']} within 500 m. "
                 f"<!-- collision-ok: {ov['share_snapping_to_an_osm_shelter_node'] * 100:.1f} "
                 f"— a SHARE OF DESIGNATED SITES in per cent, not a walk time in minutes; "
                 f"it collides by digits only with the registered l0_walk_time_to_refuge_* medians -->")

    L += ["", "### 3.5 The reading rule (§2.6), applied", "",
          f"- |Δ `naive_into_FA_safe`| = **{d_fa}** against a threshold of {thr_fa:.2f} "
          f"(a third of the OSM arm's {o['naive_into_FA_safe']}).",
          f"- |Δ `no_safe_route`| = **{d_ns}** against a threshold of {thr_ns:.2f} "
          f"(a third of the OSM arm's {o['no_safe_route']}).", "",
          f"**Verdict: {verdict}.**", "",
          "### 3.6 What this run does NOT show", "",
          "- It says nothing about the paired fire-blind versus forecast-aware contrast. Both "
          "arms of that contrast route to the same refuge set, whichever set it is, so changing "
          "the refuge set moves both together. This is a sensitivity of the ABSOLUTE rates only.",
          "- None of the 사물주소 categories is a designated **wildfire** refuge — they are "
          "earthquake, tsunami and heat. Whether a listed site would be opened, staffed or large "
          "enough during a spring wildfire is unknown (NH-012 b, `docs/juso_yeongdeok.md`).",
          "- It does not say which refuge set is correct. The designated list is an agency record "
          "of 2025-03-01; OSM is a volunteer record of 2026-07-24. Neither was verified on the ground.",
          "- The grading inherits every assumption of `docs/regrade_three_way.md` A1–A6: fire "
          "exposure under the model's own admissibility rule rather than road passability, "
          "never-detected cells assumed unaffected, node sampling only. No count here is a safety rate.",
          "- Nothing here is registered in `docs/NUMBERS.json` and nothing is on a judge-facing surface."]

    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n",
                   encoding="utf-8")
    print("\n".join(L))
    print(f"\nwrote {OUT.relative_to(REPO)}; guarded artifacts unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
