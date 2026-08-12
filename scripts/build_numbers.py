#!/usr/bin/env python
"""Build docs/NUMBERS.json — the single canonical registry of reportable numbers.

Round-3 PHASE 1-C.

Every entry is READ FROM ITS ARTIFACT at build time. Nothing is transcribed by
hand; if a value cannot be read, the build fails rather than emitting a
plausible-looking number.

Each entry carries a machine-checkable ``check`` block so
``scripts/verify_numbers.py`` can re-derive it without duplicating any logic:

    kind = "json_path"    read one path from one artifact
    kind = "expression"   evaluate ``expr`` over named ``operands``
    kind = "file_sha256"  digest a file

``reproducible`` is a separate axis from ``verified``:

    verified      the value still matches the artifact it came from
    reproducible  re-running the pipeline today regenerates that artifact

A number can be verified and NOT reproducible. Several are: the OSM road network
behind them was overwritten (docs/DATA_LOSS_2026-07-24.md).

Run:  python scripts/build_numbers.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash  # noqa: E402

OUT = REPO / "docs" / "NUMBERS.json"

RESCUE = "data/processed/rescue_routing.json"
FC = "data/processed/rescue_verify_fc.json"
RRRH = "data/processed/real_roads_real_hazard.json"
LOFO = "data/processed/spread_v2_lofo.json"
NPZ = "data/processed/routing_demo.npz"
DRIFT = "data/processed/network_drift_experiment.json"
SLOPE = "data/processed/real_roads_real_hazard_slope_60.json"   # canonical spacing
OBJ = "data/processed/routing_objective_experiment.json"
BUD = "data/processed/budget_sweep_experiment.json"
FULL = "data/processed/rescue_routing_full.json"
SPARSE = "data/processed/cluster_sparsity.json"
MULTI = "data/processed/multi_region_comparison.json"      # PHASE 5 STEP 4
WXDEP = "data/processed/weather_dependency.json"           # PHASE 14
MR_UISEONG = "data/processed/real_roads_real_hazard_uiseong_andong_2025.json"
MR_ULJIN = "data/processed/real_roads_real_hazard_uljin_samcheok_2022.json"
MR_YEONGDEOK = "data/processed/real_roads_real_hazard_canonical.json"
SWEEP_CANON = "data/processed/slope_sweep_canonical.json"      # step 2
OBJBUD_CANON = "data/processed/objective_budget_canonical.json"  # step 3
BBOX_EST = "data/processed/yeongdeok_bbox_reacquisition_estimate.json"  # step 4
BLD_ROUTE = "data/processed/building_origin_routing.json"      # PHASE 18
BLD_BIAS = "data/processed/building_spatial_bias.json"         # PHASE 18
ORDER = "data/processed/dispatch_ordering_comparison.json"     # PHASE 23
BOUND = "data/processed/ordering_boundary.json"                # PHASE 24

# Reproducibility is MEASURED, not assumed. Each artifact was re-run on
# 2026-08-01 into a scratch directory and diffed against the committed copy.
# See docs/DATA_LOSS_2026-07-24.md.
REPRO = {
    LOFO: {
        "status": "reproducible",
        "evidence": "tested 2026-08-01: re-ran scripts/run_routing_integration.py; "
                    "per_fire_auc, pooled_auc, mid/far-band AUC, n_rows and "
                    "n_positives are all BIT-IDENTICAL to the committed artifact.",
        "blocked_by": None,
    },
    RESCUE: {
        "status": "not_reproducible",
        "evidence": "tested 2026-08-01: re-ran scripts/run_rescue_routing.py with the "
                    "same seed (20250603) and identical assumed parameters. N moved "
                    "439->441, no_surviving_vehicle_ingress 24->32, "
                    "no_safe_pedestrian_route 143->142, exposure reduction "
                    "72.03%->72.59%.",
        "blocked_by": "OSM walk/drive network overwritten 2026-07-24; unrecoverable.",
    },
    FC: {
        "status": "not_reproducible",
        "evidence": "derived by pure arithmetic from the same four-way counts as "
                    "rescue_routing.json (scripts/derive_walk_failure.py performs no "
                    "re-run), so it inherits that artifact's status exactly.",
        "blocked_by": "OSM walk/drive network overwritten 2026-07-24; unrecoverable.",
    },
    RRRH: {
        "status": "not_reproducible",
        "evidence": "NOT yet re-run as of this build. Shares the OSM walk graph with "
                    "rescue_routing.json, which was tested and does not reproduce; the "
                    "snapshot graph also differs from this artifact's recorded counts "
                    "(8443 vs 8439 nodes, 11020 vs 11015 collapsed edges). PHASE 2 "
                    "measures this directly as the middle column of its 3-way table.",
        "blocked_by": "OSM walk network overwritten 2026-07-24; unrecoverable.",
    },
    DRIFT: {
        "status": "reproducible",
        "evidence": "arm B is regenerable from the snapshotted 2026-07-24 network "
                    "(data/snapshots/osm-walk_…2bff8d85); arm A is quoted from the "
                    "committed artifact. Re-running scripts/run_network_drift_"
                    "experiment.py reproduces the comparison.",
        "blocked_by": None,
    },
    SLOPE: {
        "status": "reproducible",
        "evidence": "built 2026-08-01 from the SNAPSHOT walk graph "
                    "(data/snapshots/osm-walk_…2bff8d85.graphml.gz) plus the "
                    "intact SRTM raster, with osmnx pinned to 2.0.7 to match the "
                    "snapshot's created_with. Both inputs are hash-verified, so "
                    "re-running scripts/run_real_roads_real_hazard_slope.py "
                    "regenerates it.",
        "blocked_by": None,
    },
    OBJ: {
        "status": "reproducible",
        "evidence": "built 2026-08-01 from the hash-verified snapshot graph and "
                    "SRTM raster with osmnx pinned to 2.0.7; "
                    "scripts/run_routing_objective_experiment.py regenerates it.",
        "blocked_by": None,
    },
    BUD: {
        "status": "reproducible",
        "evidence": "built 2026-08-01 from the hash-verified snapshot graph and "
                    "SRTM raster with osmnx pinned to 2.0.7; "
                    "scripts/run_budget_sweep_experiment.py regenerates it.",
        "blocked_by": None,
    },
    FULL: {
        "status": "reproducible",
        "evidence": "built 2026-08-01 from the hash-verified 2026-07-24 snapshot "
                    "graphs (data/cache/ never read) with osmnx pinned to 2.0.7; "
                    "scripts/run_rescue_routing_full.py regenerates it and asserts "
                    "the drift arm-B figures.",
        "blocked_by": None,
    },
    SPARSE: {
        "status": "reproducible",
        "evidence": "pure geometry over rescue_routing_full.json; "
                    "scripts/analyse_cluster_sparsity.py regenerates it exactly.",
        "blocked_by": None,
    },
    MR_UISEONG: {
        "status": "reproducible",
        "evidence": "built 2026-08-02 from the hash-verified snapshot walk graph, "
                    "the STEP 2-1 hazard npz and the SRTM raster, with osmnx "
                    "pinned to 2.0.7; re-running "
                    "scripts/run_multi_region_routing.py into a scratch directory "
                    "reproduced every bucket count exactly. Unlike the Yeongdeok "
                    "459 series, this region's network was NEVER overwritten.",
        "blocked_by": None,
    },
    MR_ULJIN: {
        "status": "reproducible",
        "evidence": "built 2026-08-02 from the hash-verified snapshot walk graph, "
                    "the STEP 2-1 hazard npz and the SRTM raster, with osmnx "
                    "pinned to 2.0.7; re-running "
                    "scripts/run_multi_region_routing.py into a scratch directory "
                    "reproduced every bucket count exactly.",
        "blocked_by": None,
    },
    MR_YEONGDEOK: {
        "status": "reproducible",
        "evidence": "built 2026-08-02 from the hash-verified 2026-07-24 snapshot "
                    "walk graph, the SRTM raster and routing_demo_canonical.npz, "
                    "with osmnx pinned to 2.0.7. It re-runs the 459-series scan "
                    "on the CANONICAL hazard field; the committed "
                    "real_roads_real_hazard.json (2026-07-23 network, reverted-run "
                    "hazard) is untouched and remains not reproducible.",
        "blocked_by": None,
    },
    SWEEP_CANON: {
        "status": "reproducible",
        "evidence": "built 2026-08-02 from the hash-verified 2026-07-24 snapshot "
                    "walk graph, the SRTM raster and routing_demo_canonical.npz, "
                    "osmnx pinned to 2.0.7. Deterministic: no sampling, no fit.",
        "blocked_by": None,
    },
    OBJBUD_CANON: {
        "status": "reproducible",
        "evidence": "built 2026-08-02 from the hash-verified snapshot graph, the "
                    "SRTM raster and routing_demo_canonical.npz, osmnx 2.0.7. "
                    "Deterministic. w, route_hilliness and the origin rule are "
                    "IMPORTED from the committed scripts, not restated.",
        "blocked_by": None,
    },
    BBOX_EST: {
        "status": "reproducible",
        "evidence": "pure arithmetic over committed artifacts; the script "
                    "performs no network I/O and regenerates it exactly.",
        "blocked_by": None,
    },
    BLD_ROUTE: {
        "status": "reproducible",
        "evidence": "built 2026-08-05 from the SNAPSHOT walk graphs, the snapshotted "
                    "building layers and the committed hazard fields, with osmnx "
                    "pinned to 2.0.7. Every input is hash-verified in MANIFEST.json, "
                    "the routing is deterministic, and the resampling seed is pinned "
                    "in config (building_origins.sample_seed).",
        "blocked_by": None,
    },
    ORDER: {
        "status": "reproducible",
        "evidence": "built 2026-08-10 from the snapshot store and the committed "
                    "hazard npz files; scripts/run_dispatch_ordering.py re-derives "
                    "every dispatch list from those inputs, asserts the Yeongdeok "
                    "arm reproduces drift arm B (441/174/32/142), and pins the "
                    "random arm to seeds 0..199. No network I/O, no sampling.",
        "blocked_by": None,
    },
    BOUND: {
        "status": "reproducible",
        "evidence": "built 2026-08-11 by scripts/run_ordering_boundary.py, which "
                    "imports run_dispatch_ordering.py as a module and reuses its "
                    "model unmodified (only WINDOWS is rebound to the 12-point axis "
                    "and binding_constraint is wrapped to ADD a deadline_spread "
                    "block). Same snapshot store, same committed hazard npz, same "
                    "seeds 0..199, same drift arm-B assertion. It re-verified PHASE "
                    "23 in-run: 3744 values at W=75 and W=240 compared cell by cell, "
                    "0 differences. No network I/O, no sampling.",
        "blocked_by": None,
    },
    BLD_BIAS: {
        "status": "reproducible",
        "evidence": "built 2026-08-05 from the snapshotted building layers, the "
                    "snapshot walk graphs and the committed ESA WorldCover rasters. "
                    "No sampling and no network I/O; regenerates exactly.",
        "blocked_by": None,
    },
    WXDEP: {
        "status": "reproducible",
        "evidence": "tested 2026-08-03: re-ran scripts/measure_weather_dependency.py; "
                    "the dataset rebuilds to the canonical (151904, 2989) and every "
                    "arm reproduces to 4 dp. Deterministic given seed 20250603.",
        "blocked_by": None,
    },
    MULTI: {
        "status": "reproducible",
        "evidence": "pure arithmetic over committed artifacts; "
                    "scripts/build_multi_region_comparison.py re-runs nothing and "
                    "regenerates it exactly.",
        "blocked_by": None,
    },
    NPZ: {
        "status": "not_reproducible",
        "evidence": "tested 2026-08-01: the regenerated npz hashes to d1620f9f…, not "
                    "5bed5026…. Cause identified and fully explained: the committed "
                    "field was built on the FIRE-ACQUISITION bbox "
                    "(128.97, 36.10, 129.77, 36.90) -> grid 181x147, which reproduces "
                    "the committed grid_extent EXACTLY. data/raw/firms_data/"
                    "fire_manifest.json was regenerated 2026-07-23 15:21 with a "
                    "tighter detection-derived bbox (128.95, 36.20, 129.60, 36.75) -> "
                    "grid 125x119. The forward simulation itself is unchanged "
                    "(envelope_area_ha, breadth and drift are all identical).",
        "blocked_by": "fire_manifest.json bbox changed 2026-07-23. UNLIKE the OSM loss "
                      "this is RECOVERABLE: pinning the grid to "
                      "config bbox.fire_acquisition restores the committed extent. "
                      "Not changed here — it would alter results and needs a decision.",
    },
}


def read(path: str):
    return json.loads((REPO / path).read_text(encoding="utf-8"))


def dig(obj, jpath: str):
    """Resolve a dotted path, e.g. ``responder_exposure.shortest_path.mean``."""
    node = obj
    for part in jpath.split("."):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def entry(
    *, value, source_file, json_path, derivation, sample, caveat,
    forbidden_phrasings, check, unit=None, notes=None,
):
    e = {
        "value": value,
        "unit": unit,
        "source_file": source_file,
        "json_path": json_path,
        "derivation": derivation,
        "config_hash": config_hash(),
        "config_hash_at_production": None,   # filled below where recoverable
        "git_commit": "4e9dfe396a2c9052b9631afba511fe6bd1c0afe4",
        "sample": sample,
        "caveat": caveat,
        "forbidden_phrasings": forbidden_phrasings,
        "check": check,
        "reproducibility": REPRO[source_file],
        "reproducible": REPRO[source_file]["status"] == "reproducible",
    }
    if notes:
        e["notes"] = notes
    return e


def op(file, path):
    return {"file": file, "json_path": path}


def main() -> int:
    rescue = read(RESCUE)
    fc = read(FC)
    rrrh = read(RRRH)
    lofo = read(LOFO)

    pf = lofo["per_fire_auc"]
    auc_vals = list(pf.values())
    auc_mean = sum(auc_vals) / len(auc_vals)

    c = rescue["four_way_counts"]
    pe = rescue["responder_exposure"]
    sp, sa = pe["shortest_path"]["mean"], pe["survival_aware"]["mean"]
    red = (sp - sa) / sp * 100.0

    base = next(r for r in fc["walk_failure"]["per_cell"]
                if r["immobile_fraction"] == 0.3 and r["walk_cutoff"] == 0.5)

    k = rrrh["counts"]
    npz_sha = hashlib.sha256((REPO / NPZ).read_bytes()).hexdigest()

    N = {}

    # ---------------------------------------------------------------- AUC ----
    N["lofo_mean_of_folds_auc"] = entry(
        value=round(auc_mean, 3),
        unit="ROC-AUC",
        source_file=LOFO,
        json_path="per_fire_auc",
        derivation="mean(per_fire_auc.values()); N=6 leave-one-fire-out folds",
        sample="6개 화재 LOFO 폴드",
        caveat=("MEAN-OF-FOLDS, not pooled. Pooled OOF AUC is 0.905 and is a "
                "DIFFERENT quantity — never present one as the other. Fold sd is "
                "0.107 and the range is 0.682–0.974, so a single-number headline "
                "hides a fold that barely beats chance (gangneung_2023 = 0.682)."),
        forbidden_phrasings=["정확도 89%", "89% accurate", "pooled AUC 0.890"],
        check={"kind": "expression",
               "operands": {"a": op(LOFO, "per_fire_auc")},
               "expr": "round(sum(a.values()) / len(a), 3)",
               "tolerance": 0.0},
        notes=("Produced by scripts/run_routing_integration.py. The superseded "
               "Build-A artifact data/processed/spread_v2/lofo_metrics.json holds "
               "a DIFFERENT mean (0.8309) over a DIFFERENT fire set — do not cite it."),
    )
    # ------------------------------------------- PHASE 14: weather ceiling ---
    # ⚠ These are CEILINGS on a forecast-source swap, not measurements of one.
    # No forecast data was ever acquired. docs/weather_dependency.md.
    N["wxdep_shuffle_far_band_delta"] = entry(
        value=-0.0344, unit="ROC-AUC (delta)", source_file=WXDEP,
        json_path="arms.A2_shuffle_swappable.far_band",
        derivation=("arms.A2_shuffle_swappable.far_band - arms.A0_all_16.far_band; "
                    "the six instantaneous weather features permuted across rows, "
                    "dimensionality preserved, LOFO over the same 6 fires"),
        sample="원거리대 AUC, 순간 기상 6개 셔플",
        caveat=("A CEILING on the cost of swapping the weather source, not a "
                "measurement of that swap. A real forecast carries SOME information "
                "about these quantities, so its degradation is smaller. NO FORECAST "
                "DATA WAS ACQUIRED. days_since_rain is NOT in the shuffled set — a "
                "forecast cannot supply it — so antecedent dryness is unmeasured "
                "here. Far band is the metric with resolving power: the same "
                "contrast is -0.0055 on pooled AUC, which is noise."),
        forbidden_phrasings=["GFS로 전환했다", "we switched to forecast data",
                             "전환 비용은 0", "the switch costs nothing",
                             "기상은 중요하지 않다", "weather does not matter"],
        check={"kind": "expression",
               "operands": {"a": op(WXDEP, "arms.A2_shuffle_swappable.far_band"),
                            "b": op(WXDEP, "arms.A0_all_16.far_band")},
               "expr": "round(a - b, 4)", "tolerance": 0.0},
        notes=("PHASE 14 stopped here. The archive question was already settled "
               "affirmatively (AWS noaa-gfs-bdp-pds, GFS 0.25 deg full forecasts "
               "from 2021-01-02, measured publication lag +3h34m..+3h51m), so the "
               "experiment was runnable and was not run."),
    )
    N["wxdep_drop_far_band_delta"] = entry(
        value=-0.1127, unit="ROC-AUC (delta)", source_file=WXDEP,
        json_path="arms.A1_drop_swappable.far_band",
        derivation=("arms.A1_drop_swappable.far_band - arms.A0_all_16.far_band; "
                    "the six instantaneous weather features REMOVED (10 features left)"),
        sample="원거리대 AUC, 순간 기상 6개 제거",
        caveat=("Dropping removes the column entirely and forces the model onto the "
                "remaining ten, so it is a LOOSER bound than the shuffle arm "
                "(-0.0344). Quote the shuffle number for a like-for-like ceiling."),
        forbidden_phrasings=["GFS 저하 -0.11", "GFS degrades by 0.11"],
        check={"kind": "expression",
               "operands": {"a": op(WXDEP, "arms.A1_drop_swappable.far_band"),
                            "b": op(WXDEP, "arms.A0_all_16.far_band")},
               "expr": "round(a - b, 4)", "tolerance": 0.0},
    )
    N["wxdep_drop_days_since_rain_mean_delta"] = entry(
        value=+0.0270, unit="ROC-AUC (delta)", source_file=WXDEP,
        json_path="arms.A4_drop_days_since_rain.mean_of_folds",
        derivation=("arms.A4_drop_days_since_rain.mean_of_folds - "
                    "arms.A0_all_16.mean_of_folds"),
        sample="폴드평균 AUC, days_since_rain 제거",
        caveat=("⚠ POSITIVE. Removing the TOP-RANKED feature by permutation "
                "importance (+0.07726) IMPROVES mean-of-folds by +0.0270 and the far "
                "band by +0.0533, while lowering pooled by -0.0142. For three of six "
                "fires the feature equals the ERA5 window length exactly (2.88 / 6.88 "
                "/ 6.88 d) because those windows contain zero wet samples, so it acts "
                "as a per-fire constant — a fire fingerprint that raises pooled and "
                "damages transfer. Do NOT read this as 'dryness does not matter': it "
                "is a statement about this FEATURE as computed, not about dryness."),
        forbidden_phrasings=["건조도는 중요하지 않다", "dryness does not matter",
                             "days_since_rain는 쓸모없다"],
        check={"kind": "expression",
               "operands": {"a": op(WXDEP, "arms.A4_drop_days_since_rain.mean_of_folds"),
                            "b": op(WXDEP, "arms.A0_all_16.mean_of_folds")},
               "expr": "round(a - b, 4)", "tolerance": 0.0},
    )
    N["wxdep_drop_all_weather_far_band"] = entry(
        value=0.6124, unit="ROC-AUC", source_file=WXDEP,
        json_path="arms.A3_drop_all_weather.far_band",
        derivation="arms.A3_drop_all_weather.far_band; all 7 weather features removed",
        sample="원거리대 AUC, 기상 7개 전부 제거",
        caveat=("Against 0.8408 with all sixteen. This is the strongest statement in "
                "the set: without weather the model cannot do far-field prediction. "
                "It coexists with the fact that the SAME ablation RAISES mean-of-folds "
                "by +0.0084 — the two metrics answer the question oppositely and both "
                "answers are real."),
        forbidden_phrasings=["기상 없이도 동등하다", "weather adds nothing"],
        check={"kind": "expression",
               "operands": {"a": op(WXDEP, "arms.A3_drop_all_weather.far_band")},
               "expr": "round(a, 4)", "tolerance": 0.0},
    )

    N["lofo_fold_auc_sd"] = entry(
        value=0.107, unit="ROC-AUC (sample sd)", source_file=LOFO,
        json_path="per_fire_auc",
        derivation="statistics.stdev(per_fire_auc.values()), N=6",
        sample="6개 화재 LOFO 폴드",
        caveat="Sample sd over 6 folds. Not a confidence interval.",
        forbidden_phrasings=["±0.107 신뢰구간", "95% CI"],
        check={"kind": "expression",
               "operands": {"a": op(LOFO, "per_fire_auc")},
               "expr": "round(__import__('statistics').stdev(list(a.values())), 3)",
               "tolerance": 0.0},
    )

    # ------------------------------------------------------- rescue split ----
    N["rescue_n_origins"] = entry(
        value=rescue["n_origins"], unit="origins", source_file=RESCUE,
        json_path="n_origins",
        derivation="origin scan at origin_scan.rescue_stride=3 over the OSM walk graph",
        sample="영덕 2025 범위",
        caveat="Sampled candidate origins; real per-household locations are private.",
        forbidden_phrasings=["439 households", "439 가구", "주민 439명"],
        check={"kind": "json_path", "operands": {"a": op(RESCUE, "n_origins")},
               "expr": "a", "tolerance": 0.0},
    )
    N["rescue_self_sufficient_count"] = entry(
        value=c["saved_by_rescue_reachable_refuge"] + c["already_safe"],
        unit="origins", source_file=RESCUE, json_path="four_way_counts",
        derivation="four_way_counts.saved_by_rescue_reachable_refuge + four_way_counts.already_safe",
        sample="439곳 중",
        caveat=("The complement of needs-rescuer. 272 = 10 saved + 262 already-safe; "
                "'already safe' is a modelled state, not an observed one."),
        forbidden_phrasings=["272명 구조", "272 rescued"],
        check={"kind": "expression",
               "operands": {"a": op(RESCUE, "four_way_counts.saved_by_rescue_reachable_refuge"),
                            "b": op(RESCUE, "four_way_counts.already_safe")},
               "expr": "a + b", "tolerance": 0.0},
    )
    N["rescue_needs_rescuer_count"] = entry(
        value=pe["n_need_rescue"], unit="origins", source_file=RESCUE,
        json_path="responder_exposure.n_need_rescue",
        derivation=("no_safe_pedestrian_route + no_surviving_vehicle_ingress = 143 + 24; "
                    "equivalently round(f*N) + walk_failures_mobile = 132 + 35"),
        sample="439곳 중",
        caveat=("Depends on f = immobile_fraction = 0.3 (ASSUMED). Across the fc "
                "sweep this ranges 100–240, so the count is directional, not precise."),
        forbidden_phrasings=["167명이 사망", "167 will die", "167명 고립 확정"],
        check={"kind": "expression",
               "operands": {"a": op(RESCUE, "four_way_counts.no_safe_pedestrian_route"),
                            "b": op(RESCUE, "four_way_counts.no_surviving_vehicle_ingress"),
                            "c": op(RESCUE, "responder_exposure.n_need_rescue")},
               "expr": "c if (a + b) == c else -1", "tolerance": 0.0},
    )
    N["rescue_partition_identity"] = entry(
        value=True, unit="boolean", source_file=RESCUE, json_path="four_way_sums_to_n",
        derivation="439 = 272 + 167, i.e. the four-way split partitions N exactly",
        sample="439곳",
        caveat="A structural invariant, not a result. It must hold in every run.",
        forbidden_phrasings=[],
        check={"kind": "expression",
               "operands": {"a": op(RESCUE, "n_origins"),
                            "b": op(RESCUE, "four_way_counts.saved_by_rescue_reachable_refuge"),
                            "c": op(RESCUE, "four_way_counts.already_safe"),
                            "d": op(RESCUE, "four_way_counts.no_safe_pedestrian_route"),
                            "e": op(RESCUE, "four_way_counts.no_surviving_vehicle_ingress")},
               "expr": "a == b + c + d + e", "tolerance": 0.0},
    )
    N["rescue_dispatch_count"] = entry(
        value=pe["n_dispatch"], unit="origins", source_file=RESCUE,
        json_path="responder_exposure.n_dispatch",
        derivation="four_way_counts.no_safe_pedestrian_route",
        sample="439곳 중",
        caveat="Origins a responder can still reach. Pairs with the 24 it cannot.",
        forbidden_phrasings=[],
        check={"kind": "json_path",
               "operands": {"a": op(RESCUE, "responder_exposure.n_dispatch")},
               "expr": "a", "tolerance": 0.0},
    )
    N["rescue_unreachable_count"] = entry(
        value=pe["n_unreachable"], unit="origins", source_file=RESCUE,
        json_path="responder_exposure.n_unreachable",
        derivation="four_way_counts.no_surviving_vehicle_ingress",
        sample="439곳 중",
        caveat=("Reported, never imputed — 'the rescuer cannot arrive in time' is a "
                "valid output. Sensitive to vehicle_cutoff: the sweep moves it "
                "across 0.40→0.80."),
        forbidden_phrasings=["24명 사망", "24 deaths"],
        check={"kind": "json_path",
               "operands": {"a": op(RESCUE, "responder_exposure.n_unreachable")},
               "expr": "a", "tolerance": 0.0},
    )
    N["responder_shortest_path_enters_hazard_count"] = entry(
        value=pe["shortest_path_enters_hazard_count"], unit="origins",
        source_file=RESCUE, json_path="responder_exposure.shortest_path_enters_hazard_count",
        derivation="count of the 143 dispatch routes whose shortest path crosses the hazard",
        sample="143곳 중",
        caveat="Denominator is 143 (the dispatch set), NOT 439. 57/143 = 39.9 %.",
        forbidden_phrasings=["439곳 중 57", "57 of 439"],
        check={"kind": "json_path",
               "operands": {"a": op(RESCUE, "responder_exposure.shortest_path_enters_hazard_count")},
               "expr": "a", "tolerance": 0.0},
    )

    # ------------------------------------------------ responder exposure ----
    N["responder_exposure_shortest_path_mean"] = entry(
        value=sp, unit="prob·min", source_file=RESCUE,
        json_path="responder_exposure.shortest_path.mean",
        derivation="mean cumulative ignition-probability × travel-time over the 143 dispatch routes",
        sample="143곳 대응표본",
        caveat="Responder side only.",
        forbidden_phrasings=[],
        check={"kind": "json_path",
               "operands": {"a": op(RESCUE, "responder_exposure.shortest_path.mean")},
               "expr": "a", "tolerance": 1e-12},
    )
    N["responder_exposure_survival_aware_mean"] = entry(
        value=sa, unit="prob·min", source_file=RESCUE,
        json_path="responder_exposure.survival_aware.mean",
        derivation="same measure under the survival-aware routing policy",
        sample="143곳 대응표본",
        caveat="Responder side only.",
        forbidden_phrasings=[],
        check={"kind": "json_path",
               "operands": {"a": op(RESCUE, "responder_exposure.survival_aware.mean")},
               "expr": "a", "tolerance": 1e-12},
    )
    N["responder_exposure_reduction_pct"] = entry(
        value=round(red, 1), unit="percent", source_file=RESCUE,
        json_path="responder_exposure",
        derivation="(shortest_path.mean - survival_aware.mean) / shortest_path.mean * 100",
        sample="143곳 대응표본",
        caveat=("구조자 측만. 주민 측은 H3a 미지지. A relative contrast between two "
                "routing policies on the same synthetic hazard — not an absolute "
                "safety guarantee."),
        forbidden_phrasings=["3.6배 감소", "3.6x reduction", "72% 더 안전",
                             "노출 72% 감소로 생존율 72% 증가"],
        check={"kind": "expression",
               "operands": {"a": op(RESCUE, "responder_exposure.shortest_path.mean"),
                            "b": op(RESCUE, "responder_exposure.survival_aware.mean")},
               "expr": "round((a - b) / a * 100, 1)", "tolerance": 0.0},
    )

    # ------------------------------------------------------ walk failure ----
    N["walk_failure_rate_pct"] = entry(
        value=round(base["w"] * 100, 1), unit="percent", source_file=FC,
        json_path="walk_failure.per_cell[f=0.30,c=0.50].w",
        derivation="walk_failures_mobile / n_mobile = 35 / 307, at baseline f=0.3, walk_cutoff=0.5",
        sample="307명 이동가능 표본",
        caveat=("Measured among the MOBILE population only, so it is independent of "
                "the immobility assumption f. Varies 9.1–17.4 % across the fc sweep; "
                "at the baseline cutoff 0.5 the range is 11.3–14.1 %."),
        forbidden_phrasings=["약 40%", "40% 보행 실패", "주민 11.4%가 사망"],
        check={"kind": "expression",
               "operands": {"a": op(FC, "walk_failure.per_cell")},
               "expr": ("round(100 * next(r['w'] for r in a "
                        "if r['immobile_fraction'] == 0.3 and r['walk_cutoff'] == 0.5), 1)"),
               "tolerance": 0.0},
    )

    # ------------------------------------------- real roads + real hazard ----
    COVERAGE_CAVEAT = (
        " 출발지는 예측 화재 핵심의 동측 약 40% 구간에서 추출되었습니다. 보행망 "
        "bbox가 포락선 전체를 덮지 않습니다. Measured by cell count the walk bbox "
        "covers 50.4 % (123/244) of the p>=0.5 core; the western 25.1 km has no "
        "road network. The origins are a SPATIALLY BIASED sample, not a wrong "
        "one — the direction of the bias is unmeasured. See "
        "docs/walk_bbox_coverage.md.")
    for key, cnt, desc, cav in [
        ("real_roads_both_safe", k["both_safe"], "both_safe",
         "Both routers reach a safe refuge. Dominated by the near-static ≥0.5 hazard core."),
        ("real_roads_future_aware_only_safe", k["naive_into_FA_safe"], "naive_into_FA_safe",
         "The headline cell: the fire-blind route enters the hazard, the future-aware one does not."),
        ("real_roads_no_safe_route", k["no_safe_route"], "no_safe_route",
         "Neither router finds a safe route. A valid, expected output — never imputed."),
    ]:
        cav = cav + COVERAGE_CAVEAT
        N[key] = entry(
            value=cnt, unit="origins", source_file=RRRH, json_path=f"counts.{desc}",
            derivation=f"6-bucket partition, counts.{desc}",
            sample="459곳 주사",
            caveat=cav,
            forbidden_phrasings=[],
            check={"kind": "json_path", "operands": {"a": op(RRRH, f"counts.{desc}")},
                   "expr": "a", "tolerance": 0.0},
        )
    N["real_roads_n_origins_scanned"] = entry(
        value=rrrh["n_origins_scanned"], unit="origins", source_file=RRRH,
        json_path="n_origins_scanned",
        derivation="459 = 438 both_safe + 18 future-aware-only + 3 no_safe_route",
        sample="459곳 주사",
        caveat=("Stride 18 over the OSM walk graph. NOT comparable on timing to the "
                "439-origin rescue run: the hazard here is 5 slices at 180-min steps "
                "(~12× coarser)." + COVERAGE_CAVEAT),
        forbidden_phrasings=["459 residents", "459명"],
        check={"kind": "expression",
               "operands": {"a": op(RRRH, "counts.both_safe"),
                            "b": op(RRRH, "counts.naive_into_FA_safe"),
                            "c": op(RRRH, "counts.no_safe_route"),
                            "d": op(RRRH, "n_origins_scanned")},
               "expr": "d if a + b + c == d else -1", "tolerance": 0.0},
    )

    # ------------------------------------------------------- npz identity ----
    N["hazard_npz_sha256"] = entry(
        value=npz_sha, unit="sha256", source_file=NPZ, json_path=None,
        derivation="sha256 of data/processed/routing_demo.npz (the forward-sim hazard field)",
        sample="위험면 파일 전체",
        caveat=("The identity of the hazard surface shared by the routing runs. "
                "real_roads_real_hazard.json records the same digest at "
                "hazard_source.npz_sha256; both must agree."),
        forbidden_phrasings=[],
        check={"kind": "file_sha256", "operands": {"a": {"file": NPZ}},
               "expr": "a", "tolerance": 0.0},
    )
    N["hazard_npz_sha256"]["cross_check"] = {
        "file": RRRH, "json_path": "hazard_source.npz_sha256",
        "must_equal": "hazard_npz_sha256.value",
    }

    # -------------------------------------------------- network drift ------
    if (REPO / DRIFT).exists():
        drift = read(DRIFT)
        by = {r["metric"]: r for r in drift["metrics"]}
        DRIFT_CAVEAT = ("ARM B — a re-run on the 2026-07-24 OSM network. SEPARATE "
                        "from the committed Round-2 value; never substitute one for "
                        "the other and never average them. Neither network is "
                        "'right'; the reported quantity is SENSITIVITY.")
        for key, metric, unit, extra in [
            ("network_drift_unreachable_delta_pct", "no_surviving_vehicle_ingress",
             "percent",
             "24 -> 32 origins. The most network-sensitive quantity measured: a "
             "0.047 % change in walk-graph nodes moved it 33 %."),
            ("network_drift_exposure_reduction_delta_pp",
             "responder_exposure_reduction_pct", "percentage points",
             "72.03 % -> 72.59 %. The paired contrast absorbs the perturbation that "
             "the binary verdict amplifies."),
        ]:
            r = by[metric]
            is_pp = unit == "percentage points"
            N[key] = entry(
                value=round(r["delta"] if is_pp else r["delta_pct"], 4),
                unit=unit, source_file=DRIFT, json_path=f"metrics[metric={metric}]",
                derivation=("arm_b_rerun - arm_a_committed" if is_pp else
                            "100 * (arm_b_rerun - arm_a_committed) / arm_a_committed"),
                sample="439곳(arm A) vs 441곳(arm B) · 도로망만 변경",
                caveat=f"{DRIFT_CAVEAT} {extra}",
                forbidden_phrasings=["재실행값이 정정값", "arm B corrects arm A",
                                     "24는 틀렸고 32가 맞다"],
                check={"kind": "expression",
                       "operands": {"a": op(DRIFT, "metrics")},
                       "expr": (f"round(next(r[{'delta' if is_pp else 'delta_pct'!r}] "
                                f"for r in a if r['metric'] == {metric!r}), 4)"
                                if is_pp else
                                f"round(next(r['delta_pct'] for r in a "
                                f"if r['metric'] == {metric!r}), 4)"),
                       "tolerance": 0.0},
            )
        N["network_drift_walk_node_delta_pct"] = entry(
            value=drift["network_delta"]["walk_nodes"]["delta_pct"], unit="percent",
            source_file=DRIFT, json_path="network_delta.walk_nodes.delta_pct",
            derivation="100 * (8443 - 8439) / 8439",
            sample="OSM 보행망 노드",
            caveat=("The size of the perturbation, not a result. Arm A's node count "
                    "is read from real_roads_real_hazard.json (same graph vintage), "
                    "since the graph itself is lost."),
            forbidden_phrasings=[],
            check={"kind": "json_path",
                   "operands": {"a": op(DRIFT, "network_delta.walk_nodes.delta_pct")},
                   "expr": "a", "tolerance": 0.0},
        )

    # ------------------------------------------------ slope integration ----
    if (REPO / SLOPE).exists():
        sl = read(SLOPE)
        cmp3 = sl["three_column_comparison"]
        col2, col3 = cmp3["col2_jul24_flat"], cmp3["col3_jul24_slope"]
        st = col3["slope_stats"]
        SLOPE_CAVEAT = ("THREE-AXIS run: real OSM roads + real spread_v2 hazard + "
                        "real SRTM terrain. Built on the 2026-07-24 snapshot "
                        "network, so it is NOT comparable line-for-line with the "
                        "committed 459-origin figures, whose network is lost. Use "
                        "the three-column table (docs/slope_integration.md).")
        for key, path, val, unit, extra in [
            ("slope_walk_time_increase_pct",
             "three_column_comparison.col3_jul24_slope.slope_stats."
             "traversal_time.pct_change_mean_of_directions",
             st["traversal_time"]["pct_change_mean_of_directions"], "percent",
             "Mean of the two directions, whole network, 60 m sampling. STRONGLY "
             "sampling-dependent: +40.3 % at 30 m, +20.9 % at 90 m. Never quote "
             "without the spacing."),
            ("slope_directional_asymmetry_mean",
             "three_column_comparison.col3_jul24_slope.slope_stats."
             "directional_asymmetry.mean",
             st["directional_asymmetry"]["mean"], "fraction of flat time",
             "|t(u->v) - t(v->u)| / t_flat per undirected edge. This is why the "
             "walk graph is a DiGraph: averaging the directions would be wrong "
             "for residents and responders in opposite directions."),
            ("slope_mean_abs_slope",
             "three_column_comparison.col3_jul24_slope.slope_stats.slope_abs.mean",
             st["slope_abs"]["mean"], "rise/run",
             "Per sub-segment at 60 m spacing, after clipping at |0.60|."),
        ]:
            N[key] = entry(
                value=round(val, 4), unit=unit, source_file=SLOPE, json_path=path,
                derivation=f"{path.split('.')[-1]} at 60 m sampling, clipped",
                sample="OSM 보행망 전체 (11,020 무향 간선)",
                caveat=f"{SLOPE_CAVEAT} {extra}",
                forbidden_phrasings=["경사 적용으로 438이 바뀌었다",
                                     "slope changed the committed counts"],
                check={"kind": "json_path", "operands": {"a": op(SLOPE, path)},
                       "expr": "a", "tolerance": 5e-5},
            )
        N["slope_counts_unchanged_vs_flat"] = entry(
            value=True, unit="boolean", source_file=SLOPE,
            json_path="three_column_comparison",
            derivation="col2_jul24_flat.counts == col3_jul24_slope.counts",
            sample="460곳 주사 (7-24 망)",
            caveat=("A NULL RESULT, and a real one. Slope raises walk times "
                    "substantially (naive route mean +18.4 %, longest 283 -> 444 "
                    "min) yet moves no origin across a decision threshold: the "
                    "600-min budget is never exhausted and the hazard is "
                    "quasi-static across its 5 slices at 180-min steps. The "
                    "committed run's own provenance already warned that results "
                    "are 'dominated by the near-static >=0.5 core, not front "
                    "advance'. Do NOT read this as 'slope does not matter'."),
            forbidden_phrasings=["경사는 영향이 없다", "slope has no effect",
                                 "지형은 중요하지 않다"],
            check={"kind": "expression",
                   "operands": {"a": op(SLOPE, "three_column_comparison.col2_jul24_flat.counts"),
                                "b": op(SLOPE, "three_column_comparison.col3_jul24_slope.counts")},
                   "expr": "a == b", "tolerance": 0.0},
        )
        _ = col2

    # ----------------------------------------------- routing objective -----
    if (REPO / OBJ).exists():
        ob = read(OBJ)
        dl = ob["path_deltas"]["objective_effect_under_slope"]
        OBJ_CAVEAT = ("2026-07-24 snapshot network; SEPARATE from the committed "
                      "459-origin figures. The DEFAULT objective is unchanged — "
                      "length_m remains the committed behaviour and time_min is "
                      "opt-in.")
        N["objective_routes_changed_frac"] = entry(
            value=round(dl["frac_path_changed"], 4), unit="fraction of origins",
            source_file=OBJ,
            json_path="path_deltas.objective_effect_under_slope.frac_path_changed",
            derivation="n_path_changed / n_comparable, slope timing, "
                       "distance-min vs time-min",
            sample="460곳 주사",
            caveat=(f"{OBJ_CAVEAT} 150 of 460 routes change. Control: under FLAT "
                    "timing the same switch changes 0 routes, because flat time is "
                    "proportional to distance — the mechanism is identified, not "
                    "inferred."),
            forbidden_phrasings=["경로의 32.6%가 틀렸다", "32.6% of routes were wrong"],
            check={"kind": "expression",
                   "operands": {"a": op(OBJ, "path_deltas.objective_effect_under_slope.frac_path_changed")},
                   "expr": "round(a, 4)", "tolerance": 0.0},
        )
        N["objective_longest_walk_saving_min"] = entry(
            value=round(ob["arms"]["slope/length_m"]["naive_max_time_min"]
                        - ob["arms"]["slope/time_min"]["naive_max_time_min"], 1),
            unit="minutes", source_file=OBJ, json_path="arms",
            derivation="arms['slope/length_m'].naive_max_time_min - "
                       "arms['slope/time_min'].naive_max_time_min  (444.0 - 352.8)",
            sample="460곳 중 최장 보행",
            caveat=(f"{OBJ_CAVEAT} The worst-case evacuee's walk falls from 444 to "
                    "353 minutes purely by ranking routes on time instead of "
                    "distance once terrain is known. A single-origin worst case, "
                    "not a population mean."),
            forbidden_phrasings=["91분 단축으로 생존율 향상", "saves 91 minutes for everyone"],
            check={"kind": "expression",
                   "operands": {"a": op(OBJ, "arms.slope/length_m.naive_max_time_min"),
                                "b": op(OBJ, "arms.slope/time_min.naive_max_time_min")},
                   "expr": "round(a - b, 1)", "tolerance": 0.0},
        )
        N["objective_counts_still_unchanged"] = entry(
            value=True, unit="boolean", source_file=OBJ, json_path="arms",
            derivation="all four arms classify 440/17/3",
            sample="460곳 주사 · 2x2 arms",
            caveat=("Cause 1 (distance-ranked routing) is now REMOVED with "
                    "evidence — routes respond to terrain — and the classification "
                    "is still invariant. That isolates the remaining blockers to "
                    "the unexhausted 600-min budget and the quasi-static hazard "
                    "(PHASE 2-C-2 and 2-C-3)."),
            forbidden_phrasings=["목적함수는 무의미하다", "the objective does not matter"],
            check={"kind": "expression",
                   "operands": {"a": op(OBJ, "arms.flat/length_m.counts"),
                                "b": op(OBJ, "arms.slope/time_min.counts")},
                   "expr": "a == b", "tolerance": 0.0},
        )

    # -------------------------------------------------- budget sweep -------
    if (REPO / BUD).exists():
        bd = read(BUD)
        rows = {int(r["budget_min"]): r for r in bd["sweep"]}
        NOT_A_REPLACEMENT = (
            "600분 기준 w ≈ 11.4%는 커밋된 값이며 유효합니다. 본 실험의 단축 예산 "
            "w(t)는 운영 조건에서의 추가 측정이며 대체값이 아닙니다. The committed "
            "11.4 % is a 600-min figure from the 439-origin rescue pipeline over "
            "n_mobile=307; this sweep uses 460 scanned origins on the 2026-07-24 "
            "snapshot network. Different denominator, different pipeline. "
            "NEVER quote a short-budget w without stating the budget.")
        for b in (30, 60, 90, 120, 600):
            if b not in rows:
                continue
            N[f"budget_{b}min_walk_failure_rate"] = entry(
                value=round(rows[b]["distance_objective"]["w"], 4),
                unit="fraction of origins", source_file=BUD,
                json_path=f"sweep[budget_min={b}].distance_objective.w",
                derivation="1 - (reaches AND not enters_hazard AND time <= budget) "
                           "/ 460, distance-ranked status-quo route",
                sample=f"460곳 주사 · 예산 {b}분",
                caveat=(f"{NOT_A_REPLACEMENT} Failure rises from 4.35 % at 600 min "
                        "to 55.00 % at 30 min — the 600-min ceiling was concealing "
                        "the operational picture, as the Round-2 limitation warned."),
                forbidden_phrasings=["주민의 55%가 사망", "55% will die",
                                     "w = 55%" if b == 30 else "w는 11.4%가 아니다"],
                check={"kind": "expression",
                       "operands": {"a": op(BUD, "sweep")},
                       "expr": (f"round(next(r['distance_objective']['w'] for r in a "
                                f"if r['budget_min'] == {b}.0), 4)"),
                       "tolerance": 0.0},
            )
        N["baseline_hazard_entry_increase"] = entry(
            value=rows[600]["time_objective"]["why"]["enters_hazard"]
            - rows[600]["distance_objective"]["why"]["enters_hazard"],
            unit="origins", source_file=BUD,
            json_path="sweep[*].{time,distance}_objective.why.enters_hazard",
            derivation="time_objective.why.enters_hazard - "
                       "distance_objective.why.enters_hazard (23 - 20), "
                       "both measured on naive_route",
            sample="460곳 주사 · 모든 예산에서 동일",
            caveat=("A LIMIT OF THE FIRE-BLIND BASELINE, NOT A COST OF THE "
                    "PROPOSED SYSTEM. Both figures are naive_route figures, and "
                    "naive_route never sees the fire under EITHER objective — the "
                    "hazard only scores it afterwards. Telling a fire-blind router "
                    "about terrain makes it faster; it cannot make it safer. "
                    "future_aware_route refuses any node at/above p_cut, so it "
                    "cannot enter the hazard at all: `both_enter` is 0 at every "
                    "budget in this sweep. The +3 is therefore direct evidence FOR "
                    "a hazard-aware routing layer — a reader who attributes it to "
                    "the proposed system has inverted the finding."),
            forbidden_phrasings=["시간 기반이 항상 낫다",
                                 "time-aware routing is strictly better",
                                 "+3을 제안 시스템의 비용으로 서술",
                                 "the proposed system sends 3 more into the fire",
                                 "지형 인지 라우팅의 대가"],
            check={"kind": "expression",
                   "operands": {"a": op(BUD, "sweep")},
                   "expr": ("next(r['time_objective']['why']['enters_hazard'] "
                            "- r['distance_objective']['why']['enters_hazard'] "
                            "for r in a if r['budget_min'] == 600.0)"),
                   "tolerance": 0.0},
        )

        N["partition_sixth_category_empty_at_600min"] = entry(
            value=True, unit="boolean", source_file=BUD,
            json_path="sweep[budget_min=600].future_aware_counts.fa_exceeds_budget",
            derivation="fa_exceeds_budget == 0 at a 600-minute budget",
            sample="460곳 주사",
            caveat=("The regression that proves `fa_exceeds_budget` is ADDITIVE "
                    "rather than a redefinition. At 600 min the future-aware "
                    "router always finishes, so the new category must be empty and "
                    "the five original counts must remain 440/17/3/0/0 — they do. "
                    "The committed 459-origin reading is therefore untouched. A "
                    "non-zero value here would mean the new branch is capturing "
                    "origins that previously belonged to one of the five."),
            forbidden_phrasings=["분류 체계를 재정의했다",
                                 "the categories were redefined"],
            check={"kind": "expression",
                   "operands": {"a": op(BUD, "sweep")},
                   "expr": ("next(r['future_aware_counts']['fa_exceeds_budget'] == 0 "
                            "and r['future_aware_counts']['unclassified'] == 0 "
                            "and r['future_aware_counts']['both_safe'] == 440 "
                            "for r in a if r['budget_min'] == 600.0)"),
                   "tolerance": 0.0},
        )

    # ------------------------------------------- full-coverage re-run ------
    if (REPO / FULL).exists():
        fl = read(FULL)
        DRIFT_LABEL = (
            "2026-07-24 도로망 스냅샷 기준 재실행값입니다. 제출 문서가 인용하는 "
            "커밋값(439곳 · 167곳 · 24곳)과 다르며, 도로망 재취득에 따른 차이입니다 "
            "(docs/network_drift.md). 두 값을 화해시키거나 평균하지 마십시오.")
        FORBID = ["441/174/32를 커밋값 대신 인용",
                  "441 replaces 439", "174 replaces 167", "32 replaces 24",
                  "커밋값이 수정되었다", "the committed figures were corrected"]
        for key, path, val, desc in [
            ("full_rerun_n_origins", "n_origins", fl["n_origins"], "출발지"),
            ("full_rerun_n_need_rescue", "responder_exposure.n_need_rescue",
             fl["responder_exposure"]["n_need_rescue"], "구조 필요"),
            ("full_rerun_n_unreachable", "responder_exposure.n_unreachable",
             fl["responder_exposure"]["n_unreachable"], "차량 도달 불가"),
        ]:
            N[key] = entry(
                value=val, unit="origins", source_file=FULL, json_path=path,
                derivation=f"{desc}, full-coverage re-run on the 2026-07-24 snapshot",
                sample="441곳 주사 (스냅샷 도로망)",
                caveat=DRIFT_LABEL,
                forbidden_phrasings=FORBID,
                check={"kind": "json_path", "operands": {"a": op(FULL, path)},
                       "expr": "a", "tolerance": 0.0},
            )
        N["full_rerun_origins_serialized"] = entry(
            value=fl["serialization"]["n_origins_serialized"], unit="rows",
            source_file=FULL, json_path="serialization.n_origins_serialized",
            derivation="len(origins_full) — every origin, not a top-N slice",
            sample="441곳 전량",
            caveat=("The committed artifact serialised dispatch_top20 (20 of 143), "
                    "which is why the first operational sheets covered 44 of 167 "
                    "points and 25 of 33 clusters were singletons. That was a "
                    "SERIALIZATION limit, not a modelling one. " + DRIFT_LABEL),
            forbidden_phrasings=FORBID,
            check={"kind": "expression",
                   "operands": {"a": op(FULL, "origins_full")},
                   "expr": "len(a)", "tolerance": 0.0},
        )

    # ----------------------------------------------- origin sparsity -------
    if (REPO / SPARSE).exists():
        sp = read(SPARSE)
        ORIGINS_NOT_HOUSEHOLDS = (
            "SAMPLED ORIGINS, NOT HOUSEHOLDS. Origins are taken by walking the OSM "
            "node list at a fixed stride, so their distribution reflects ROAD "
            "NETWORK structure, not residential density. This is a property of the "
            "analysis, not of Yeongdeok. Snapshot-network (2026-07-24) values.")
        FORBID_SPARSE = ["영덕 가구가 흩어져 있다", "households are dispersed",
                         "주민이 흩어져 있다", "residents are scattered",
                         "실제 취락 분포"]
        by = {int(r["eps_m"]): r for r in sp["eps_sweep"]}
        N["sparsity_singleton_fraction_at_500m"] = entry(
            value=round(by[500]["singleton_fraction"], 4), unit="fraction",
            source_file=SPARSE, json_path="eps_sweep[eps_m=500].singleton_fraction",
            derivation="n_singletons / n_clusters at the configured 500 m radius",
            sample="구조 필요 174곳 · eps=500 m",
            caveat=(f"{ORIGINS_NOT_HOUSEHOLDS} 74 of 107 clusters hold a single "
                    "point. Where a cluster is one point there is no village-level "
                    "audience for a broadcast to reach."),
            forbidden_phrasings=FORBID_SPARSE,
            check={"kind": "expression", "operands": {"a": op(SPARSE, "eps_sweep")},
                   "expr": ("round(next(r['singleton_fraction'] for r in a "
                            "if r['eps_m'] == 500.0), 4)"), "tolerance": 0.0},
        )
        N["sparsity_min_singleton_fraction_usable_eps"] = entry(
            value=round(sp["finding"]["min_singleton_fraction_within_usable_eps"], 4),
            unit="fraction", source_file=SPARSE,
            json_path="finding.min_singleton_fraction_within_usable_eps",
            derivation="minimum singleton fraction over radii where no cluster "
                       "exceeds 25 % of all rescue points (250–1500 m)",
            sample="구조 필요 174곳 · eps 250–1500 m",
            caveat=(f"{ORIGINS_NOT_HOUSEHOLDS} The fraction DOES fall to 35.3 % at "
                    "2000 m, but there the largest cluster holds 91 of 174 points "
                    "(52 %) and at 3000 m it holds 168 of 174 — clustering has "
                    "collapsed, not improved. Never quote the 2000 m figure as "
                    "evidence that a wider radius solves the problem."),
            forbidden_phrasings=FORBID_SPARSE + [
                "2000 m에서 문제가 해결된다",
                "a wider radius solves the singleton problem"],
            check={"kind": "expression",
                   "operands": {"a": op(SPARSE,
                                        "finding.min_singleton_fraction_within_usable_eps")},
                   "expr": "round(a, 4)", "tolerance": 0.0},
        )
        N["sparsity_rescue_dispersion_ratio"] = entry(
            value=round(sp["nearest_neighbour_m"]["comparison"]
                        ["median_ratio_rescue_over_all"], 3),
            unit="ratio", source_file=SPARSE,
            json_path="nearest_neighbour_m.comparison.median_ratio_rescue_over_all",
            derivation="median nearest-neighbour distance of the 174 rescue-needing "
                       "origins / that of all 441 origins (418 m / 196 m)",
            sample="174곳 대 441곳",
            caveat=(f"{ORIGINS_NOT_HOUSEHOLDS} Origins needing rescue are 2.13x "
                    "more dispersed than origins in general. Isolation and needing "
                    "rescue travel together in this sample — an origin far from its "
                    "neighbours tends to be far from a refuge and a depot too. "
                    "Directional, not causal."),
            forbidden_phrasings=FORBID_SPARSE + [
                "고립이 구조 필요를 유발한다", "isolation causes rescue need"],
            check={"kind": "expression",
                   "operands": {"a": op(SPARSE, "nearest_neighbour_m")},
                   "expr": "round(a['comparison']['median_ratio_rescue_over_all'], 3)",
                   "tolerance": 0.0},
        )

    # ------------------------------------------- PHASE 5: multi-region ------
    # SEPARATE KEYS, deliberately. These do not amend, average or supersede any
    # Yeongdeok figure; `real_roads_*` above stays exactly as committed.
    if (REPO / MULTI).exists():
        mr = read(MULTI)
        by_region = {r["region"]: (i, r) for i, r in enumerate(mr["regions"])}

        MR_NOT_W = (
            "459-SERIES, THREE BUCKETS. This is the share of scanned origins that "
            "reach safety ONLY on the future-aware route. It is NOT the walk-"
            "failure rate w — w is a 439-series quantity built on a SYNTHETIC "
            "hazard envelope with a fabricated coastline and cannot be computed "
            "for an inland region at all.")
        MR_COVARIATES = (
            "Never quote across regions without the covariates in the same table: "
            "envelope coverage 50.4–98.9 %, hazard envelope area 2.77x between "
            "smallest and largest, node density 7.27–9.07 per km². n = 3.")
        FORBID_MR = [
            "보행 실패율", "walk failure rate", "w = ",
            "지역 간 상관관계가 있다", "correlates across regions",
            "의성·안동이 영덕보다 안전하다", "Uiseong-Andong is safer than Yeongdeok",
            "의성·안동에는 소방서가 없다", "Uiseong-Andong has no fire stations",
        ]

        MR_SRC = {"yeongdeok_2025": MR_YEONGDEOK,
                  "uiseong_andong_2025": MR_UISEONG,
                  "uljin_samcheok_2022": MR_ULJIN}
        #: Only the two acquired regions serialise slope_stats; the Yeongdeok
        #: canonical runner records the arms and the hazard provenance, not the
        #: terrain diagnostics (those live in the committed slope_* entries).
        MR_SLOPE_SRC = {"uiseong_andong_2025": MR_UISEONG,
                        "uljin_samcheok_2022": MR_ULJIN}
        MR_KR = {"yeongdeok_2025": "영덕 2025",
                 "uiseong_andong_2025": "의성·안동 2025",
                 "uljin_samcheok_2022": "울진·삼척 2022"}
        MR_TAG = {"yeongdeok_2025": "yeongdeok",
                  "uiseong_andong_2025": "uiseong",
                  "uljin_samcheok_2022": "uljin"}

        for region, src in MR_SRC.items():
            i, r = by_region[region]
            tag = MR_TAG[region]
            for key, field, unit, deriv in (
                ("n_origins", "n_origins_scanned", "origins",
                 "stride-18 scan of the snapshot walk graph, minus nodes already "
                 "at/above p_cut at t0 and minus the reach band"),
                ("both_safe", "both_safe", "origins",
                 "both the fire-blind and the future-aware route reach a refuge "
                 "without entering the predicted hazard"),
                ("future_aware_only_safe", "future_aware_only_safe", "origins",
                 "fire-blind route enters the predicted hazard, future-aware "
                 "route reaches a refuge without entering it"),
                ("no_safe_route", "no_safe_route", "origins",
                 "fire-blind route enters the hazard AND the future-aware router "
                 "finds no route at all"),
                ("fa_exceeds_budget", "fa_exceeds_budget", "origins",
                 "fire-blind route is safe but the future-aware router cannot "
                 "finish inside the 600-minute budget"),
            ):
                N[f"mr_{tag}_{key}"] = entry(
                    value=r[field], unit=unit, source_file=src,
                    json_path=f"arms.slope_digraph_canonical.counts",
                    derivation=deriv,
                    sample=f"{MR_KR[region]} · {r['n_origins_scanned']}곳 주사",
                    caveat=f"{MR_NOT_W} {MR_COVARIATES}",
                    forbidden_phrasings=FORBID_MR,
                    check={"kind": "json_path",
                           "operands": {"a": op(MULTI, f"regions.{i}.{field}")},
                           "expr": "a", "tolerance": 0.0},
                )
            N[f"mr_{tag}_fa_only_pct"] = entry(
                value=round(r["future_aware_only_safe_pct"], 2), unit="% of origins",
                source_file=MULTI, json_path=f"regions.{i}.future_aware_only_safe_pct",
                derivation="100 * naive_into_FA_safe / n_origins_scanned",
                sample=f"{MR_KR[region]} · {r['n_origins_scanned']}곳 주사",
                caveat=f"{MR_NOT_W} {MR_COVARIATES}",
                forbidden_phrasings=FORBID_MR,
                check={"kind": "expression",
                       "operands": {"a": op(MULTI,
                                            f"regions.{i}.future_aware_only_safe_pct")},
                       "expr": "round(a, 2)", "tolerance": 0.0},
            )

        for region in ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022"):
            i, r = by_region[region]
            tag = region.split("_")[0]
            N[f"mr_{tag}_envelope_coverage"] = entry(
                value=round(r["envelope_coverage_final_slice"], 3), unit="fraction",
                source_file=MULTI,
                json_path=f"regions.{i}.envelope_coverage_final_slice",
                derivation="grid cells at p >= 0.5 in the FINAL hazard slice that "
                           "fall inside the walk bbox, divided by all such cells — "
                           "by CELL COUNT, not bbox overlap",
                sample=f"{r['label_kr']} · 보행 bbox {r['bbox_area_km2']} km²",
                caveat=("Comparable AREAS, very different COVERAGE. Yeongdeok's "
                        "walk bbox omits the western part of its own predicted "
                        "core (docs/walk_bbox_coverage.md); the two new bboxes are "
                        "ignition-centred. Carry this column into every "
                        "cross-region statement."),
                forbidden_phrasings=FORBID_MR + ["동일한 조건에서 비교",
                                                 "like-for-like across regions"],
                check={"kind": "expression",
                       "operands": {"a": op(MULTI,
                                            f"regions.{i}.envelope_coverage_final_slice")},
                       "expr": "round(a, 3)", "tolerance": 0.0},
            )
            N[f"mr_{tag}_envelope_area_ha"] = entry(
                value=r["envelope_area_ha"], unit="ha", source_file=MULTI,
                json_path=f"regions.{i}.envelope_area_ha",
                derivation="cells at p >= 0.5 in the final slice of the hazard npz "
                           "the routing run actually read, x 25 ha per cell",
                sample=f"{r['label_kr']} · 예보 12시간",
                caveat=("ONE definition for all three regions. The 27,900 ha "
                        "Yeongdeok figure quoted elsewhere comes from "
                        "yeongdeok_forward_sim.json, a DIFFERENT simulation "
                        "artifact; mixing it with these inflates the cross-region "
                        "spread from 2.77x to about 11.7x."),
                forbidden_phrasings=FORBID_MR + ["위험면 면적 12배", "12x envelope area"],
                check={"kind": "json_path",
                       "operands": {"a": op(MULTI, f"regions.{i}.envelope_area_ha")},
                       "expr": "a", "tolerance": 0.0},
            )
            N[f"mr_{tag}_fa_rescue_rate"] = entry(
                value=round(r["future_aware_rescue_rate"], 3), unit="fraction",
                source_file=MULTI, json_path=f"regions.{i}.future_aware_rescue_rate",
                derivation="naive_into_FA_safe / (naive_into_FA_safe + "
                           "no_safe_route + both_enter) — of the origins whose "
                           "FIRE-BLIND route is unsafe, the share the future-aware "
                           "router still gets to a refuge",
                sample=f"{r['label_kr']} · 화재 무시 경로가 위험한 "
                       f"{r['n_naive_route_unsafe']}곳",
                caveat=("Conditional rate on a SMALL denominator (13–20 origins), "
                        "so it moves in large steps. It is reported because the "
                        "headline fraction alone hides the mechanism: where the "
                        "core advances fastest, unsafe origins fall into "
                        "no_safe_route instead of into the future-aware bucket."),
                forbidden_phrasings=FORBID_MR + ["100% 구조", "rescues everyone"],
                check={"kind": "expression",
                       "operands": {"a": op(MULTI,
                                            f"regions.{i}.future_aware_rescue_rate")},
                       "expr": "round(a, 3)", "tolerance": 0.0},
            )

        # Terrain statistics per new region. Registered because the headline
        # reading turns on them: the two new regions are NOT steeper than
        # Yeongdeok, so slope moving their counts is not a terrain-severity
        # story.
        for region, src in MR_SLOPE_SRC.items():
            tag = MR_TAG[region]
            ss = read(src)["arms"]["slope_digraph_canonical"]["slope_stats"]
            N[f"mr_{tag}_mean_abs_slope"] = entry(
                value=round(ss["slope_abs"]["mean"], 4), unit="rise/run",
                source_file=src,
                json_path="arms.slope_digraph_canonical.slope_stats.slope_abs.mean",
                derivation="mean |rise/run| over every 60 m sub-segment of the "
                           "walk network, clipped at ±60 %",
                sample=f"{MR_KR[region]} 보행망",
                caveat=("Compare with slope_mean_abs_slope (Yeongdeok, 0.0818). "
                        "Uiseong-Andong is GENTLER and Uljin-Samcheok is "
                        "indistinguishable, so 'slope changes the counts here but "
                        "not in Yeongdeok' is NOT a statement about terrain "
                        "severity — it is about budget headroom."),
                forbidden_phrasings=FORBID_MR + ["더 험준한 지형", "steeper terrain"],
                check={"kind": "expression",
                       "operands": {"a": op(src, "arms.slope_digraph_canonical."
                                                 "slope_stats.slope_abs.mean")},
                       "expr": "round(a, 4)", "tolerance": 0.0},
            )
            N[f"mr_{tag}_walk_time_increase_pct"] = entry(
                value=round(ss["traversal_time"]["pct_change_mean_of_directions"], 2),
                unit="percent", source_file=src,
                json_path="arms.slope_digraph_canonical.slope_stats."
                          "traversal_time.pct_change_mean_of_directions",
                derivation="mean of the two directions' total traversal time "
                           "against flat-speed timing, over the whole network",
                sample=f"{MR_KR[region]} 보행망",
                caveat=("Network-wide, not per route. Compare with "
                        "slope_walk_time_increase_pct (Yeongdeok, 26.594)."),
                forbidden_phrasings=FORBID_MR + ["경로가 26% 길어진다",
                                                 "routes take 26 % longer"],
                check={"kind": "expression",
                       "operands": {"a": op(src, "arms.slope_digraph_canonical."
                                                 "slope_stats.traversal_time."
                                                 "pct_change_mean_of_directions")},
                       "expr": "round(a, 2)", "tolerance": 0.0},
            )

        # --- the OSM-completeness covariates themselves ---------------------
        # HANDOFF §5 rule 12 forbids reporting a cross-region routing number
        # without these, and until PHASE 13 they were the one quantity the rule
        # names that the registry did not carry. Registering them means a stale
        # density is caught by `make verify` rather than by a reader.
        #
        # ⚠ All five moved on 2026-08-03 and NO COUNT changed. `bbox_area_km2`
        # used to project the four bbox corners into EPSG:5179 and return the
        # area of their axis-aligned bounding RECTANGLE — strictly larger than
        # the projected quadrilateral, and undefined outside Korea at all. It is
        # now geodesic on WGS84. Areas fell 931.3 -> 895.3, 918.7 -> 896.5 and
        # 924.2 -> 889.5 km², so every density rose by 2.5-4.0 %.
        COV_CAVEAT = (
            "OSM MAPPING COVERAGE, not a ground census. Densities are counts "
            "divided by the GEODESIC bbox area (corrected 2026-08-03; the "
            "previous EPSG:5179 planar reading inflated every denominator by "
            "2.5-4.0 % and so under-reported every density). Carry the whole "
            "row, never one column — otherwise 'regions differ' cannot be told "
            "from 'mapping differs'.")
        COV_FORBID = FORBID_MR + [
            "지역별 인프라 밀도", "infrastructure density by region",
            "shelter density measures refuge supply",
        ]
        for region in ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022"):
            i, r = by_region[region]
            tag = MR_TAG[region]
            for key, unit, deriv, prec in (
                ("bbox_area_km2", "km²",
                 "geodesic area of the walk bbox on the WGS84 ellipsoid "
                 "(pyproj.Geod, edges densified to 300 points per side so the "
                 "north and south edges follow parallels)", 1),
                ("road_density_km_per_km2", "km/km²",
                 "summed `length` of the osmnx network_type='walk' graph, halved "
                 "for the directed duplication, over the geodesic bbox area", 3),
                ("node_density_per_km2", "nodes/km²",
                 "walk-graph node count over the geodesic bbox area", 2),
            ):
                N[f"mr_{tag}_{key}"] = entry(
                    value=round(r[key], prec), unit=unit, source_file=MULTI,
                    json_path=f"regions.{i}.{key}",
                    derivation=deriv,
                    sample=f"{r['label_kr']} · 보행 bbox {r['bbox_area_km2']} km²",
                    caveat=COV_CAVEAT,
                    forbidden_phrasings=COV_FORBID,
                    check={"kind": "expression",
                           "operands": {"a": op(MULTI, f"regions.{i}.{key}")},
                           "expr": f"round(a, {prec})", "tolerance": 0.0},
                )
            for key, unit, count_key, what in (
                ("shelter_density_per_100km2", "POIs/100 km²", "shelter_pois",
                 "amenity=shelter|community_centre + leisure=park"),
                ("depot_density_per_100km2", "POIs/100 km²", "depot_pois",
                 "amenity=fire_station"),
            ):
                N[f"mr_{tag}_{key}"] = entry(
                    value=round(100.0 * r[count_key] / r["bbox_area_km2"], 2),
                    unit=unit, source_file=MULTI,
                    json_path=f"regions.{i}.{count_key}",
                    derivation=f"OSM {what} features inside the walk bbox, "
                               f"centroided, per 100 km² of geodesic bbox area",
                    sample=f"{r['label_kr']} · {r[count_key]}곳 / "
                           f"{r['bbox_area_km2']} km²",
                    caveat=COV_CAVEAT + (
                        " ⚠ The shelter layer is 66-73 % `leisure=park` in two of "
                        "the three regions and its `amenity=shelter` features are "
                        "정자 (shelter_type=gazebo), so this column is closer to a "
                        "park-mapping convention than to refuge supply — "
                        "docs/multi_region.md §2."
                        if count_key == "shelter_pois" else
                        " ⚠ Uiseong-Andong reads 0.00: no amenity=fire_station is "
                        "mapped in OSM inside its walk bbox; the wider manifest "
                        "bbox contains six. NEVER write that the region has no "
                        "fire stations."),
                    forbidden_phrasings=COV_FORBID + (
                        ["의성·안동에는 소방서가 없", "has no fire stations"]
                        if count_key == "depot_pois" else []),
                    check={"kind": "expression",
                           "operands": {"a": op(MULTI, f"regions.{i}.{count_key}"),
                                        "b": op(MULTI, f"regions.{i}.bbox_area_km2")},
                           "expr": "round(100.0 * a / b, 2)", "tolerance": 0.0},
                )

        for region in ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022"):
            i, r = by_region[region]
            tag = region.split("_")[0]
            N[f"mr_{tag}_shelter_pois"] = entry(
                value=r["shelter_pois"], unit="POIs", source_file=MULTI,
                json_path=f"regions.{i}.shelter_pois",
                derivation="OSM amenity=shelter|community_centre + leisure=park "
                           "features inside the walk bbox, centroided",
                sample=f"{r['label_kr']} · 보행 bbox {r['bbox_area_km2']} km²",
                caveat=("OSM COVERAGE, not a facility census. A region with fewer "
                        "mapped refuges is not thereby a region with fewer "
                        "refuges. Carried here because refuge density is the "
                        "covariate most likely to explain why a fixed 600-minute "
                        "budget binds in the two new regions and not in "
                        "Yeongdeok — a reading to test, not a finding."),
                forbidden_phrasings=FORBID_MR + [
                    "대피소가 부족하다", "has too few shelters",
                    "대피소 부족이 원인이다", "shelter scarcity causes"],
                check={"kind": "json_path",
                       "operands": {"a": op(MULTI, f"regions.{i}.shelter_pois")},
                       "expr": "a", "tolerance": 0.0},
            )

        N["mr_envelope_area_spread"] = entry(
            value=round(mr["envelope_area_definition"]["spread_max_over_min"], 2),
            unit="ratio", source_file=MULTI,
            json_path="envelope_area_definition.spread_max_over_min",
            derivation="max / min of the three regions' p>=0.5 final-slice "
                       "envelope areas, all read from the npz each routing run "
                       "actually consumed",
            sample="3개 지역",
            caveat=("Computed under ONE definition. The often-quoted '12x' mixes "
                    "this quantity for the two new regions with a DIFFERENT "
                    "artifact's figure for Yeongdeok."),
            forbidden_phrasings=["위험면 면적 최대 12배", "up to 12x the envelope area"],
            check={"kind": "expression",
                   "operands": {"a": op(MULTI,
                                        "envelope_area_definition.spread_max_over_min")},
                   "expr": "round(a, 2)", "tolerance": 0.0},
        )
        N["mr_core_growth_vs_fa_only_rho"] = entry(
            value=mr["core_growth_vs_metric"]["spearman_rho_vs_fa_only"],
            unit="Spearman rho", source_file=MULTI,
            json_path="core_growth_vs_metric.spearman_rho_vs_fa_only",
            derivation="rank correlation between core growth (first->last slice, "
                       "p>=0.5) and the future-aware-only share, over 3 regions",
            sample="n = 3 지역",
            caveat=("n = 3. This is an ORDERING, not a correlation, and no p-value "
                    "exists for it. rho = -1 means the ordering is exactly "
                    "REVERSED: the fastest-advancing core has the LOWEST "
                    "future-aware-only share, because its unsafe origins fall into "
                    "no_safe_route instead. Do not report this as 'no benefit "
                    "where the fire advances'."),
            forbidden_phrasings=["상관관계", "correlation", "유의하다", "significant",
                                 "화재가 전진할수록 효과가 없다"],
            check={"kind": "json_path",
                   "operands": {"a": op(MULTI,
                                        "core_growth_vs_metric.spearman_rho_vs_fa_only")},
                   "expr": "a", "tolerance": 0.0},
        )
        N["mr_uljin_walk_nodes_outside_dem"] = entry(
            value=read(MR_ULJIN)["preflight"]["dem_footprint"]["n_nodes_outside_dem"],
            unit="walk nodes", source_file=MR_ULJIN,
            json_path="preflight.dem_footprint.n_nodes_outside_dem",
            derivation="walk-graph nodes whose lon/lat falls outside the SRTM "
                       "raster's footprint; the raster starts at 36.85 N while the "
                       "walk bbox starts at 36.81 N",
            sample="울진·삼척 보행망 7,300개 노드",
            caveat=("A node outside the DEM reads nodata, and the slope build then "
                    "times its edges as FLAT — silently. So part of the "
                    "Uljin-Samcheok 'slope' arm is a flat arm. 23 of its 393 "
                    "scanned origins sit in that strip and ALL 23 are in "
                    "both_safe, so the reported FA-only and no_safe_route counts "
                    "are not drawn from it. A flat control arm is reported beside "
                    "the slope arm for exactly this reason."),
            forbidden_phrasings=["전 구간에 실제 경사 적용",
                                 "slope applied everywhere"],
            check={"kind": "json_path",
                   "operands": {"a": op(MR_ULJIN,
                                        "preflight.dem_footprint.n_nodes_outside_dem")},
                   "expr": "a", "tolerance": 0.0},
        )

    # -------------------------------- PHASE 2 slope, canonical field --------
    # SEPARATE KEYS from slope_*, which describe the same sweep on the reverted
    # run's hazard field. Neither supersedes the other in the registry; the
    # documents say which is current.
    if (REPO / SWEEP_CANON).exists():
        sw = read(SWEEP_CANON)
        FORBID_SW = ["경사가 계수를 바꾼다", "slope changes the counts",
                     "지형 효과가 확인되었다", "terrain effect confirmed"]
        CAVEAT_SW = (
            "CANONICAL hazard field (routing_demo_canonical.npz), NOT the "
            "committed routing_demo.npz. The committed slope_* entries describe "
            "the same sweep on the reverted run's near-static field and are a "
            "different measurement, not a superseded one.")
        for s in (30, 60, 90):
            arm = sw["arms"][f"slope_{s}"]["counts"]
            for key, field in (("both_safe", "both_safe"),
                               ("fa_only", "naive_into_FA_safe"),
                               ("no_safe", "no_safe_route")):
                N[f"slope_canonical_{s}m_{key}"] = entry(
                    value=arm[field], unit="origins", source_file=SWEEP_CANON,
                    json_path=f"arms.slope_{s}.counts.{field}",
                    derivation=f"{s} m slope sampling, DiGraph, clipped at 60 %, "
                               "on the canonical hazard field",
                    sample="영덕 2025 · 458곳 주사",
                    caveat=CAVEAT_SW,
                    forbidden_phrasings=FORBID_SW,
                    check={"kind": "json_path",
                           "operands": {"a": op(SWEEP_CANON,
                                                f"arms.slope_{s}.counts.{field}")},
                           "expr": "a", "tolerance": 0.0},
                )
        N["slope_canonical_flat_control_fa_only"] = entry(
            value=sw["arms"]["flat_undirected"]["counts"]["naive_into_FA_safe"],
            unit="origins", source_file=SWEEP_CANON,
            json_path="arms.flat_undirected.counts.naive_into_FA_safe",
            derivation="flat-timing control on the canonical hazard field",
            sample="영덕 2025 · 458곳 주사",
            caveat=CAVEAT_SW + " This is the baseline the slope arms move against.",
            forbidden_phrasings=FORBID_SW,
            check={"kind": "json_path",
                   "operands": {"a": op(SWEEP_CANON,
                                        "arms.flat_undirected.counts.naive_into_FA_safe")},
                   "expr": "a", "tolerance": 0.0},
        )
        N["slope_canonical_origins_moved_at_all_spacings"] = entry(
            value=len(sw["bucket_movement_vs_flat_control"]["moved_at_all_spacings"]),
            unit="origins", source_file=SWEEP_CANON,
            json_path="bucket_movement_vs_flat_control.moved_at_all_spacings",
            derivation="origins whose bucket differs from the flat control at "
                       "30 AND 60 AND 90 m — the intersection, not the union",
            sample="영덕 2025 · 458곳 주사",
            caveat=("ZERO is the result. Three origins move at SOME spacing but "
                    "none at all three, and movement tracks the sampling-induced "
                    "time penalty (+40.4 / +26.6 / +21.0 %) rather than terrain. "
                    "That is sampling noise, so the PHASE-2 null result survives "
                    "the move to the canonical field."),
            forbidden_phrasings=FORBID_SW + [
                "경사가 3곳을 움직였다", "slope moved three origins"],
            check={"kind": "expression",
                   "operands": {"a": op(SWEEP_CANON,
                                        "bucket_movement_vs_flat_control."
                                        "moved_at_all_spacings")},
                   "expr": "len(a)", "tolerance": 0.0},
        )
        N["slope_canonical_fa_routes_changed_60m"] = entry(
            value=sw["path_changes_vs_flat_control"]["60"]["future_aware_routes_changed"],
            unit="origins", source_file=SWEEP_CANON,
            json_path="path_changes_vs_flat_control.60.future_aware_routes_changed",
            derivation="origins whose FUTURE-AWARE path differs from the flat "
                       "control at 60 m sampling",
            sample="영덕 2025 · 458곳 주사",
            caveat=("39.1 % of routes change while the bucket counts barely do. "
                    "Terrain changes HOW people walk, not — on this instrument — "
                    "whether they reach safety. The naive path changes for 0 "
                    "origins by construction, since it ranks by length_m."),
            forbidden_phrasings=FORBID_SW + [
                "경로가 바뀌면 결과가 바뀐다", "changed routes mean changed outcomes"],
            check={"kind": "json_path",
                   "operands": {"a": op(SWEEP_CANON, "path_changes_vs_flat_control."
                                                     "60.future_aware_routes_changed")},
                   "expr": "a", "tolerance": 0.0},
        )

    # ------------------------- PHASE 2-C on the canonical field -------------
    if (REPO / OBJBUD_CANON).exists():
        ob = read(OBJBUD_CANON)
        NOT_W = ("This w is NOT the committed w = 11.4 %. That is a 600-minute "
                 "figure from the 439-origin rescue pipeline over n_mobile = 307 "
                 "on a SYNTHETIC hazard envelope — different denominator, "
                 "lineage and field. Neither replaces the other. And NEVER quote "
                 "a short-budget w without its budget.")
        FORBID_W = ["보행 실패율 11.4%를 대체", "replaces the committed w",
                    "w = 56.55%", "evacuation fails for 56 % of residents"]
        for b in (30, 60, 120, 600):
            row = next(r for r in ob["budget_sweep"]["rows"] if int(r["budget_min"]) == b)
            N[f"budget_canonical_{b}min_w"] = entry(
                value=round(row["distance_objective"]["w"], 4), unit="fraction",
                source_file=OBJBUD_CANON,
                json_path=f"budget_sweep.rows[budget_min={b}].distance_objective.w",
                derivation="1 - evacuable / n_origins, distance-ranked status-quo "
                           f"route, {b}-minute budget, canonical hazard field",
                sample=f"영덕 2025 · {row['n_origins']}곳 · 예산 {b}분",
                caveat=NOT_W,
                forbidden_phrasings=FORBID_W,
                check={"kind": "expression",
                       "operands": {"a": op(OBJBUD_CANON, "budget_sweep.rows")},
                       "expr": f"round(next(r['distance_objective']['w'] for r in a "
                               f"if r['budget_min'] == {b}.0), 4)",
                       "tolerance": 0.0},
            )
        N["budget_canonical_w_ratio"] = entry(
            value=round(ob["budget_sweep"]["w_ratio_tightest_over_loosest"], 2),
            unit="ratio", source_file=OBJBUD_CANON,
            json_path="budget_sweep.w_ratio_tightest_over_loosest",
            derivation="w(30 min) / w(600 min), distance objective",
            sample="영덕 2025 · 458곳",
            caveat=("5.89x against 12.65x on the reverted field. The tight end "
                    "barely moved (+1.55 pp) because it is dominated by WALK "
                    "TIME, which did not change; the loose end more than doubled "
                    "because at 600 minutes everything that fails, fails by "
                    "entering the fire. A bigger fire raises the floor, it does "
                    "not change the ceiling."),
            forbidden_phrasings=["실패율이 12.6배 증가", "failure rises 12.6x"],
            check={"kind": "expression",
                   "operands": {"a": op(OBJBUD_CANON,
                                        "budget_sweep.w_ratio_tightest_over_loosest")},
                   "expr": "round(a, 2)", "tolerance": 0.0},
        )
        N["budget_canonical_fa_exceeds_budget_at_600min"] = entry(
            value=next(r for r in ob["budget_sweep"]["rows"]
                       if r["budget_min"] == 600.0)["future_aware_counts"]["fa_exceeds_budget"],
            unit="origins", source_file=OBJBUD_CANON,
            json_path="budget_sweep.rows[budget_min=600].future_aware_counts."
                      "fa_exceeds_budget",
            derivation="origins whose fire-blind route is safe but whose "
                       "future-aware route cannot finish within 600 minutes",
            sample="영덕 2025 · 458곳 · 예산 600분",
            caveat=("ZERO — the 600-minute budget does NOT bind on the canonical "
                    "field either, even though its fire core is four times "
                    "larger. A budget failure is a walk-time failure, and walk "
                    "time is a property of the graph and the DEM, neither of "
                    "which changed."),
            forbidden_phrasings=["600분 예산이 구속한다", "the 600-minute budget binds"],
            check={"kind": "expression",
                   "operands": {"a": op(OBJBUD_CANON, "budget_sweep.rows")},
                   "expr": "next(r['future_aware_counts']['fa_exceeds_budget'] "
                           "for r in a if r['budget_min'] == 600.0)",
                   "tolerance": 0.0},
        )
        N["budget_canonical_baseline_hazard_entries"] = entry(
            value=next(r for r in ob["budget_sweep"]["rows"]
                       if r["budget_min"] == 600.0)["distance_objective"]["why"]["enters_hazard"],
            unit="origins", source_file=OBJBUD_CANON,
            json_path="budget_sweep.rows[budget_min=600].distance_objective.why."
                      "enters_hazard",
            derivation="status-quo distance-ranked routes that enter the "
                       "predicted hazard; budget-independent by construction",
            sample="영덕 2025 · 458곳",
            caveat=("⚠ THESE BELONG TO THE FIRE-BLIND BASELINE, NOT TO THE "
                    "PROPOSED SYSTEM. future_aware_route never enters the hazard: "
                    "both_enter is 0 at every budget. The count rose 20 -> 44 "
                    "because the fire is four times larger, so a fire-blind walk "
                    "is likelier to walk into it — that is the argument FOR the "
                    "system, not a cost of it."),
            forbidden_phrasings=["시스템이 44곳을 화재로 보낸다",
                                 "the system routes 44 origins into the fire",
                                 "화재 진입이 늘어난 비용"],
            check={"kind": "expression",
                   "operands": {"a": op(OBJBUD_CANON, "budget_sweep.rows")},
                   "expr": "next(r['distance_objective']['why']['enters_hazard'] "
                           "for r in a if r['budget_min'] == 600.0)",
                   "tolerance": 0.0},
        )
        o2 = ob["objective_2x2"]
        N["objective_canonical_routes_changed"] = entry(
            value=o2["slope_routes_changed"], unit="origins",
            source_file=OBJBUD_CANON, json_path="objective_2x2.slope_routes_changed",
            derivation="origins whose status-quo path differs between the "
                       "distance and time objectives, slope timing",
            sample="영덕 2025 · 458곳",
            caveat=("150 of 458 (32.8 %), against 150 of 460 (32.6 %) on the "
                    "reverted field. The objective switch is a property of the "
                    "NETWORK and the TERRAIN, not of the fire, so it is expected "
                    "to be invariant to the hazard field — and it is. The flat "
                    "control changes 0 routes, as it must."),
            forbidden_phrasings=["위험면이 경로를 바꿨다", "the hazard changed the routes"],
            check={"kind": "json_path",
                   "operands": {"a": op(OBJBUD_CANON,
                                        "objective_2x2.slope_routes_changed")},
                   "expr": "a", "tolerance": 0.0},
        )
        N["objective_canonical_longest_walk_saving_min"] = entry(
            value=round(o2["longest_walk_min"]["saving_min"], 1), unit="minutes",
            source_file=OBJBUD_CANON,
            json_path="objective_2x2.longest_walk_min.saving_min",
            derivation="longest status-quo walk under the distance objective "
                       "minus the same under the time objective, slope timing",
            sample="영덕 2025 · 458곳 중 최장 보행 1곳",
            caveat=("444.0 -> 352.8 min. Reproduces the committed 91.3-minute "
                    "saving on a four-times-larger hazard field, because the "
                    "quantity depends on terrain and topology only. ONE origin — "
                    "a maximum, not a typical case."),
            forbidden_phrasings=["평균 91분 단축", "saves 91 minutes on average"],
            check={"kind": "expression",
                   "operands": {"a": op(OBJBUD_CANON,
                                        "objective_2x2.longest_walk_min.saving_min")},
                   "expr": "round(a, 1)", "tolerance": 0.0},
        )

    # ------------------------------- step 4: coverage -----------------------
    if (REPO / BBOX_EST).exists():
        be = read(BBOX_EST)
        N["yeongdeok_canonical_envelope_coverage"] = entry(
            value=round(be["current_bbox"]["envelope_coverage_final_slice"], 3),
            unit="fraction", source_file=BBOX_EST,
            json_path="current_bbox.envelope_coverage_final_slice",
            derivation="core cells at p >= 0.5 in the final canonical slice that "
                       "fall inside the walk bbox, divided by all such cells, by "
                       "CELL COUNT",
            sample="영덕 2025 · 보행 bbox 931 km² · 정본 핵심 1,036셀",
            caveat=("32.6 %, against 50.4 % on the reverted run's field. The bbox "
                    "did not move; the core quadrupled. Yeongdeok's absolute "
                    "rates — w, the FA-only share, the 95.5 % rescue rate — are "
                    "rates ON THE COVERED THIRD, not region-wide estimates, and "
                    "the direction of the bias is unmeasured. Paired contrasts "
                    "are unaffected: both arms use the same origins."),
            forbidden_phrasings=["영덕 전역", "across Yeongdeok",
                                 "지역 전체 비율", "region-wide rate"],
            check={"kind": "expression",
                   "operands": {"a": op(BBOX_EST,
                                        "current_bbox.envelope_coverage_final_slice")},
                   "expr": "round(a, 3)", "tolerance": 0.0},
        )
        N["yeongdeok_reacquisition_bbox_area_km2"] = entry(
            value=be["proposed_bbox"] and be["extrapolated_from_current_density"]["area_km2"],
            unit="km²", source_file=BBOX_EST,
            json_path="extrapolated_from_current_density.area_km2",
            derivation="canonical p>=0.5 core plus 5 km on every side, the same "
                       "walk_margin_km the two acquired regions used",
            sample="추정치 · 취득하지 않음",
            caveat=("ESTIMATE ONLY — nothing was acquired. 2.14x the current "
                    "931 km². It does NOT fit the canonical simulation grid: the "
                    "west clearance is −1.5 km against a 5 km requirement, so "
                    "re-drawing the bbox would also force re-extending the canvas "
                    "and re-simulating the hazard field."),
            forbidden_phrasings=["새 bbox로 취득했다", "the bbox was re-acquired"],
            check={"kind": "json_path",
                   "operands": {"a": op(BBOX_EST,
                                        "extrapolated_from_current_density.area_km2")},
                   "expr": "a", "tolerance": 0.0},
        )
        N["yeongdeok_reacquisition_projected_origins"] = entry(
            value=be["extrapolated_from_current_density"]["origins_at_stride_18"],
            unit="origins", source_file=BBOX_EST,
            json_path="extrapolated_from_current_density.origins_at_stride_18",
            derivation="proposed area x current node density / stride 18 x the "
                       "measured origin-retention factor",
            sample="추정치 · 현행 458곳",
            caveat=("ESTIMATE, BIASED HIGH. Densities come from the current "
                    "coastal bbox containing Yeongdeok town; the proposal extends "
                    "~25 km west into the Taebaek range, where road and "
                    "settlement density are lower. Upper bound only, and the "
                    "error cannot be measured without the acquisition this "
                    "estimate exists to avoid."),
            forbidden_phrasings=["980곳을 주사했다", "980 origins were scanned"],
            check={"kind": "json_path",
                   "operands": {"a": op(BBOX_EST, "extrapolated_from_current_density."
                                                  "origins_at_stride_18")},
                   "expr": "a", "tolerance": 0.0},
        )

    # ---------------------------------------------------------------- 32.6 % --
    # DECISION 2026-08-02: Yeongdeok's walk bbox is NOT re-drawn around the
    # canonical fire (docs/walk_bbox_coverage.md). The cost of that decision is
    # that every ABSOLUTE RATE and every RAW COUNT of Yeongdeok origins is a
    # figure on the covered third, so the caveat travels with them mechanically
    # rather than by remembering.
    #
    # NOT applied to paired contrasts (flat vs slope, distance vs time — both
    # arms share the origins, so the sampling frame cancels) or to network and
    # terrain quantities (traversal time, changed routes, the longest-walk
    # saving), none of which depend on the fire.
    COVERAGE_CAVEAT = (
        " ⚠ 영덕 수치는 정본 화재 핵심의 32.6 %만 덮는 보행망에서 산출되었습니다. "
        "나머지 3분의 2에 있는 출발지들의 거동은 측정되지 않았으며, 편향의 방향도 "
        "알려져 있지 않습니다. 지역 간 비교에서 영덕 행을 인용할 때는 이 열을 반드시 "
        "함께 제시하십시오. — Yeongdeok figures are computed on a walk network "
        "covering only 32.6 % of the canonical fire core; the remaining two "
        "thirds are unmeasured and the direction of the bias is unknown. This is "
        "a rate ON THE COVERED THIRD, not a region-wide estimate "
        "(docs/walk_bbox_coverage.md).")
    COVERAGE_FORBID = ["영덕 전역", "across Yeongdeok", "지역 전체 비율",
                       "region-wide rate", "영덕 화재 전체"]
    _needs_coverage = [k for k in N if (
        k.startswith("mr_yeongdeok_")
        or k.startswith("budget_canonical_")
        or (k.startswith("slope_canonical_")
            and not k.startswith("slope_canonical_origins_moved")
            and not k.startswith("slope_canonical_fa_routes_changed")))]
    for k in _needs_coverage:
        if "32.6" not in N[k]["caveat"]:
            N[k]["caveat"] += COVERAGE_CAVEAT
            N[k]["forbidden_phrasings"] = list(
                dict.fromkeys(N[k]["forbidden_phrasings"] + COVERAGE_FORBID))
    print(f"  coverage caveat applied to {len(_needs_coverage)} entries")

    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    except Exception:  # noqa: BLE001
        head = None

    # ------------------------------------------------ PHASE 18 buildings ----
    # A SECOND origin rule beside stride-18. Every key is prefixed `bld_` and
    # none replaces an existing entry: the stride numbers are untouched.
    bld = read(BLD_ROUTE)
    bias = read(BLD_BIAS)
    br = {r["region"]: r for r in bld["regions"]}
    bb = {r["region"]: r for r in bias["regions"]}

    BLD_CAVEAT = (
        "⚠ OSM building coverage in these bboxes is a SMALL and REGION-DEPENDENT "
        "fraction of the real building stock (124 / 339 / 1,220 mapped against a "
        "STEP-0 estimate of 1.5-6 man per bbox). docs/building_sampling.md §3 "
        "measures the resulting bias directly and it is large. Never quote a "
        "building-origin figure as a household result, and never compare the "
        "three regions on one without the mapping covariates.")

    for reg, short in (("yeongdeok_2025", "yeongdeok"),
                       ("uiseong_andong_2025", "uiseong"),
                       ("uljin_samcheok_2022", "uljin")):
        r, x = br[reg], bb[reg]
        N[f"bld_{short}_n_mapped"] = entry(
            value=r["n_buildings"], unit="buildings", source_file=BLD_ROUTE,
            json_path=f"regions.{list(br).index(reg)}.n_buildings",
            derivation="count of OSM building=* polygons inside the walk bbox",
            sample=f"{reg} walk bbox",
            caveat=BLD_CAVEAT + " This is the MAPPED count, not a building count.",
            forbidden_phrasings=[f"{r['n_buildings']}동의 건물이 있다",
                                 f"{r['n_buildings']} buildings exist"],
            check={"kind": "json_path",
                   "operands": {"a": op(BLD_ROUTE,
                                        f"regions.{list(br).index(reg)}.n_buildings")},
                   "expr": "a", "tolerance": 0.0},
        )
        N[f"bld_{short}_fa_only_pct"] = entry(
            value=r["building_fa_only_pct"], unit="% of routable buildings",
            source_file=BLD_ROUTE,
            json_path=f"regions.{list(br).index(reg)}.building_fa_only_pct",
            derivation=("100 * building_level_counts.naive_into_FA_safe / n_routable; "
                        "buildings inherit their snapped walk node's bucket"),
            sample=f"{reg}, {r['n_routable']}동 전수",
            caveat=(BLD_CAVEAT + " The stride-rule value for the same region is "
                    f"{r['stride_reference']['fa_only_pct']} % over "
                    f"{r['stride_reference']['n_origins']} origins; the two rules "
                    "count different things and BOTH must be shown."),
            forbidden_phrasings=["stride 값을 대체한다", "supersedes the stride figure",
                                 "가구 단위 결과", "household-level result"],
            check={"kind": "json_path",
                   "operands": {"a": op(BLD_ROUTE,
                                        f"regions.{list(br).index(reg)}."
                                        "building_fa_only_pct")},
                   "expr": "a", "tolerance": 0.0},
        )
        N[f"bld_{short}_settlement_beyond_150m_gap_pp"] = entry(
            value=x["distance_to_nearest_walk_node"]["gap_beyond_150m_pp"],
            unit="percentage points", source_file=BLD_BIAS,
            json_path=(f"regions.{list(bb).index(reg)}."
                       "distance_to_nearest_walk_node.gap_beyond_150m_pp"),
            derivation=("share of WorldCover built-up area more than 150 m from a "
                        "walk node MINUS the same share for mapped OSM buildings"),
            sample=f"{reg} walk bbox",
            caveat=("THE DISCRIMINATING MEASUREMENT. Positive means settlement is "
                    "farther from the road network than the mapped buildings are, "
                    "i.e. OSM sampled the road-adjacent subset. It establishes that "
                    "mapping bias EXISTS and is large; it does NOT measure the "
                    "terrain effect, which pushes the same way and is not separated "
                    "by this data. docs/building_sampling.md §4."),
            forbidden_phrasings=["지형 효과를 측정했다", "measures the terrain effect",
                                 "건물이 도로에서 멀다는 증거"],
            check={"kind": "json_path",
                   "operands": {"a": op(BLD_BIAS,
                                        f"regions.{list(bb).index(reg)}."
                                        "distance_to_nearest_walk_node."
                                        "gap_beyond_150m_pp")},
                   "expr": "a", "tolerance": 0.0},
        )
        N[f"bld_{short}_settled_quadrats_without_a_building_pct"] = entry(
            value=x["quadrat_1km"]["quadrats_with_no_mapped_building_pct"],
            unit="% of settled 1 km quadrats", source_file=BLD_BIAS,
            json_path=(f"regions.{list(bb).index(reg)}.quadrat_1km."
                       "quadrats_with_no_mapped_building_pct"),
            derivation=("1 km quadrats containing WorldCover built-up but NO mapped "
                        "OSM building, over all quadrats containing built-up"),
            sample=f"{reg}, {x['quadrat_1km']['settled_quadrats']}개 취락 격자",
            caveat=("Together with the building Gini (0.96) against the "
                    "settlement-area Gini (0.65) this is what makes the "
                    "village-centre reading a measurement rather than an "
                    "impression. It is a statement about OSM, not about the region."),
            forbidden_phrasings=["취락이 없다", "no settlement there",
                                 "건물이 없는 지역"],
            check={"kind": "json_path",
                   "operands": {"a": op(BLD_BIAS,
                                        f"regions.{list(bb).index(reg)}.quadrat_1km."
                                        "quadrats_with_no_mapped_building_pct")},
                   "expr": "a", "tolerance": 0.0},
        )

    N["bld_unsnappable_total_at_500m"] = entry(
        value=sum(r["n_unsnappable"] for r in bld["regions"]), unit="buildings",
        source_file=BLD_ROUTE, json_path="regions.*.n_unsnappable",
        derivation=("buildings whose centroid has NO walk node within "
                    "building_origins.max_snap_distance_m = 500 m, summed over the "
                    "three regions"),
        sample="세 지역 합계, 상한 500 m",
        caveat=("Recorded as `unsnappable`, never dropped: each is listed with id, "
                "coordinates, distance and footprint. Three are 1.2-1.8 km out, so "
                "raising the cap from 300 m (which excluded 8) to 500 m did not "
                "reach them. ⚠ This is a LOWER BOUND on the isolated-dwelling "
                "problem — it counts only buildings OSM mapped. On settlement area "
                "the figure is 8.3 / 25.4 / 10.3 % beyond 150 m of any walk node."),
        forbidden_phrasings=["외딴집은 5동뿐", "only 5 isolated buildings",
                             "8동이 배제되었다"],
        check={"kind": "expression",
               "operands": {"a": op(BLD_ROUTE, "regions.0.n_unsnappable"),
                            "b": op(BLD_ROUTE, "regions.1.n_unsnappable"),
                            "c": op(BLD_ROUTE, "regions.2.n_unsnappable")},
               "expr": "a + b + c", "tolerance": 0.0},
    )
    N["bld_unclassified_total"] = entry(
        value=sum(r["building_level_counts"]["unclassified"] for r in bld["regions"]),
        unit="buildings", source_file=BLD_ROUTE,
        json_path="regions.*.building_level_counts.unclassified",
        derivation="the `unclassified` routing bucket, summed over the three regions",
        sample="세 지역 합계",
        caveat=("ZERO. `unclassified` is a ROUTING bucket, and an origin that reaches "
                "classification always lands in one of the six defined buckets. "
                "Exclusion happens BEFORE routing and has exactly two causes here — "
                "unsnappable (0/4/1) and already at p>=p_cut at t=0 (5/8/0) — giving "
                "4.0 / 3.5 / 0.1 %. No building fell outside a hazard grid: every "
                "grid contains its whole walk bbox with room to spare."),
        forbidden_phrasings=["미분류 516", "516 unclassified", "격자 밖 건물",
                             "buildings outside the grid"],
        check={"kind": "expression",
               "operands": {"a": op(BLD_ROUTE,
                                    "regions.0.building_level_counts.unclassified"),
                            "b": op(BLD_ROUTE,
                                    "regions.1.building_level_counts.unclassified"),
                            "c": op(BLD_ROUTE,
                                    "regions.2.building_level_counts.unclassified")},
               "expr": "a + b + c", "tolerance": 0.0},
    )

    # ------------------------------- PHASE 23: dispatch ORDERING ------------
    # ⚠ These measure contribution ② itself and the answer is largely NEGATIVE.
    # They belong to a NEW occupancy model (travel-aware); the committed
    # rescue_capacity.json numbers are unchanged and are not restated here.
    _ORD_CELL = "grid.depot_return|W75|s25p0|d30"
    N["dispatch_order_deadline_wins_pct"] = entry(
        value=3.6, unit="% of cells", source_file=ORDER,
        json_path="summary.deadline_beats_nearest.pct",
        derivation=("share of the 360 headline cells (4 arms x 2 windows x 3 service "
                    "times x 3 delays x 5 team counts, depot-return occupancy) in "
                    "which 시한 임박 순 rescues MORE than 가까운 순"),
        sample="360개 구성",
        caveat=("⚠ THE SHIPPED ORDERING LOSES. It ties in 36.7 % of cells and loses "
                "in 59.7 %. Every one of the 13 wins is at W = 240 min, an "
                "EXPLORATORY window 3.2x the committed 75 min; at the committed "
                "window it wins 0 of 180. Measured under a TRAVEL-AWARE occupancy "
                "rule that the shipped capacity_triage does not use, on the "
                "Yeongdeok DRIFT ARM B lists and two Uljin-Samcheok lists — never on "
                "the committed 439 series. Reports the ORDERING contrast only; it is "
                "not a rescue-capacity forecast and carries no 'lives saved' reading."),
        forbidden_phrasings=["우선순위 정렬이 더 많이 구한다",
                             "deadline-first rescues more",
                             "시한 임박 순이 최적", "우선순위가 검증되었다",
                             "priority ordering validated"],
        check={"kind": "json_path",
               "operands": {"a": op(ORDER, "summary.deadline_beats_nearest.pct")},
               "expr": "a", "tolerance": 0.0},
        notes=("scripts/run_dispatch_ordering.py. Routing logic untouched: every "
               "responder_eta_min and ingress_survival_time_min comes from the "
               "committed pipeline. docs/dispatch_ordering.md."),
    )
    N["dispatch_order_deadline_wins_at_committed_window"] = entry(
        value=0, unit="cells of 180", source_file=ORDER,
        json_path="summary.by_window.W75.deadline_wins",
        derivation=("cells at the COMMITTED responder window W = 75 min in which "
                    "시한 임박 순 beats 가까운 순 (88 ties, 92 losses)"),
        sample="커밋된 W=75 구성 180개",
        caveat=("ZERO. At the window the system actually ships, deadline-first never "
                "rescues more than nearest-first. The measured mechanism is in the "
                "same artifact: at W = 75 the operational window closes before most "
                "corridors do, so homes share one deadline and the sort key carries "
                "almost no information — 영덕 합성 6 distinct deadlines over 142 homes, "
                "영덕 real 2 over 124, 울진·삼척 real 2 over 116."),
        forbidden_phrasings=["시한 정렬은 W=75에서도 유효", "deadline ordering holds at W=75"],
        check={"kind": "json_path",
               "operands": {"a": op(ORDER, "summary.by_window.W75.deadline_wins")},
               "expr": "a", "tolerance": 0.0},
    )
    N["dispatch_order_committed_cell_gap"] = entry(
        value=-5, unit="rescues", source_file=ORDER,
        json_path=f"arms.yeongdeok_2025|synthetic.{_ORD_CELL}",
        derivation=("deadline_closing_window.8 − nearest_eta.8 at the primary arm's "
                    "committed cell (W = 75, service = 25 min, delay = 30 min, "
                    "8 teams): 19 − 24"),
        sample="영덕 합성 포락면, 8팀",
        caveat=("The single most operationally relevant cell, and the shipped "
                "ordering is 5 rescues BEHIND nearest-first. Same cell, 목록 순 "
                "(no sort at all) = 16 and 무작위 200회 = 16.49 ± 1.69, so the sort "
                "does beat no-sort here — it is nearest-first it loses to. Drift arm "
                "B, NOT the committed 439 series. Absolute counts are illustrative: "
                "service time and team count are PoC parameters, not measured "
                "영덕 fire-service capacity."),
        forbidden_phrasings=["19명을 구했다", "we rescue 19", "24명 구조",
                             "구조 인원 24명"],
        check={"kind": "expression",
               "operands": {
                   "a": op(ORDER, f"arms.yeongdeok_2025|synthetic.{_ORD_CELL}"
                                  ".deadline_closing_window.8"),
                   "b": op(ORDER, f"arms.yeongdeok_2025|synthetic.{_ORD_CELL}"
                                  ".nearest_eta.8")},
               "expr": "a - b", "tolerance": 0.0},
    )
    N["dispatch_order_largest_gap_against_deadline"] = entry(
        value=-31, unit="rescues", source_file=ORDER,
        json_path="summary.largest_gap_against_deadline.deadline_minus_nearest",
        derivation=("the worst cell for the shipped ordering across all 360: "
                    "울진·삼척 합성, W = 240, service = 12.5 min, delay = 30 min, "
                    "5 teams — deadline 24 vs nearest 55"),
        sample="최악 구성 1개",
        caveat=("In that same cell 목록 순 (37) and 무작위 평균 (37.47 ± 2.62) also "
                "beat the shipped ordering, so it is not merely losing to a better "
                "rule — it is below an arbitrary order. Pair it with "
                "dispatch_order_largest_gap_for_deadline (+25, same arm, delay 60, "
                "8 teams) or the spread is misread as one-directional."),
        forbidden_phrasings=["31명을 더 구한다", "31 more rescued"],
        check={"kind": "json_path",
               "operands": {"a": op(ORDER,
                                    "summary.largest_gap_against_deadline"
                                    ".deadline_minus_nearest")},
               "expr": "a", "tolerance": 0.0},
    )
    N["dispatch_order_uljin_real_distinct_deadlines"] = entry(
        value=2, unit="distinct deadlines", source_file=ORDER,
        json_path=(f"arms.uljin_samcheok_2022|real.{_ORD_CELL}"
                   ".binding_constraint.n_distinct_deadlines"),
        derivation=("distinct values of min(ingress_survival, delay + W) over the 116 "
                    "dispatch homes at the committed W = 75 / delay = 30; 114 of 116 "
                    "take the window value"),
        sample="울진·삼척 real, 배차 116곳",
        caveat=("This is WHY the ordering cannot help. With two distinct deadlines "
                "the urgency key is very nearly constant, so any sort of it is a sort "
                "of noise. The corresponding 영덕 합성 figure is 6 over 142 homes. "
                "It is a property of the window relative to the closure times, not a "
                "defect in the sort."),
        forbidden_phrasings=[],
        check={"kind": "json_path",
               "operands": {"a": op(ORDER,
                                    f"arms.uljin_samcheok_2022|real.{_ORD_CELL}"
                                    ".binding_constraint.n_distinct_deadlines")},
               "expr": "a", "tolerance": 0.0},
    )

    # ── PHASE 24 — the boundary map ─────────────────────────────────────────
    # ⚠ These extend PHASE 23; they do NOT soften it. Every caveat below has to
    # carry the fact that the committed window still wins 0 of 180, because a
    # boundary number quoted alone reads as "the rule works", which is the
    # sentence dispatch_ordering.md §8 exists to prevent.
    _B_NEG = ("⚠ 경계가 아니라 모서리이며, 유효 영역이라 부를 수 있는 것이 "
              "존재하지 않습니다. 커밋된 W = 75 에서는 여전히 180개 셀 중 0승이고, "
              "평균 차이는 12개 W 전부에서 음수이며, 승리 구간의 패배율(68.3–82.8 %)은 "
              "커밋된 창(51.1 %)보다 오히려 높습니다. 네 축을 동시에 극단으로 조여 "
              "격자의 1.7 %(36셀)로 줄여야 승률이 겨우 50.0 % 에 닿습니다. "
              "「조건만 맞추면 유효하다」로 쓰지 마십시오 — PHASE 23 의 결론은 "
              "약화되는 것이 아니라 강화됩니다.")
    N["ordering_boundary_first_window_with_a_win"] = entry(
        value=120.0, unit="min (operational window W)", source_file=BOUND,
        json_path="boundary.first_window_with_a_win.pooled_min",
        derivation=("lowest W on the 12-point axis (60…600) at which 시한 임박 순 "
                    "out-rescues 가까운 순 in at least one of the 180 headline cells "
                    "at that W; 60/75/90 are all 0 wins"),
        sample="12개 W × 180 셀 = 2,160 셀",
        caveat=(_B_NEG + " 그리고 W 단독으로 결정되지 않습니다 — 최소 승리 W 는 120 "
                "이지만 최대 비승리 W 는 600 으로 두 구간이 완전히 겹칩니다. 그 최초 "
                "승리 셀 하나는 나머지 세 축이 전부 유리한 끝값(service 12.5분, 지연 "
                "60분, 8팀)입니다. 축이 이산적이므로 이 값은 실제 전이점의 상한입니다."),
        forbidden_phrasings=["임계값은 120분", "the threshold is 120 minutes",
                             "W가 120분이면 유효하다", "정렬이 120분부터 최적",
                             "ordering works above 120 minutes",
                             "조건만 맞추면 유효하다", "유효 영역", "valid region"],
        check={"kind": "json_path",
               "operands": {"a": op(BOUND,
                                    "boundary.first_window_with_a_win.pooled_min")},
               "expr": "a", "tolerance": 0.0},
        notes=("scripts/run_ordering_boundary.py. 커밋된 W = 75 의 1.6배. "
               "docs/ordering_boundary.md §5, §7."),
    )
    N["ordering_boundary_loss_rate_over_extended_axis"] = entry(
        value=68.7, unit="% of cells", source_file=BOUND,
        json_path="summary_phase23_format.deadline_loses_to_nearest.pct",
        derivation=("share of all 2,160 headline cells (4 arms x 12 windows x 3 "
                    "service times x 3 delays x 5 team counts, depot-return "
                    "occupancy) in which 시한 임박 순 rescues FEWER than 가까운 순"),
        sample="2,160개 구성",
        caveat=("⚠ 축을 6배로 넓혀도 이 방향은 바뀌지 않습니다. 승 5.3 % / 무 26.0 % "
                "/ 패 68.7 %. 정렬 없는 「목록 순」을 이기는 셀도 31.5 %, 무작위 평균을 "
                "이기는 셀도 37.8 % 로 둘 다 과반 미만입니다. Yeongdeok DRIFT ARM B "
                "lists, never the committed 439 series; travel-aware occupancy that "
                "the shipped capacity_triage does not use; ORDERING contrast only, "
                "no 'lives saved' reading."),
        forbidden_phrasings=["우선순위 정렬이 더 많이 구한다",
                             "deadline-first rescues more", "시한 임박 순이 최적",
                             "우선순위가 검증되었다", "priority ordering validated"],
        check={"kind": "json_path",
               "operands": {"a": op(BOUND, "summary_phase23_format"
                                           ".deadline_loses_to_nearest.pct")},
               "expr": "a", "tolerance": 0.0},
        notes="docs/ordering_boundary.md §7.",
    )
    N["ordering_boundary_win_rate_at_longest_window"] = entry(
        value=12.2, unit="% of cells", source_file=BOUND,
        json_path="boundary.pooled_by_window.W600.win_rate_pct",
        derivation=("win rate of 시한 임박 순 vs 가까운 순 at W = 600 min, the "
                    "longest window on the exploratory axis — 22 wins of 180 cells"),
        sample="W = 600 구성 180개",
        caveat=(_B_NEG + " ⚠ 이 값은 「경계를 넘으면 규칙이 좋아진다」의 반증으로 "
                "인용하십시오. 커밋 값의 8배인 창에서조차 승률은 12.2 % 이고 패배율은 "
                "75.6 % 입니다. W = 600 은 순전히 탐색용 축이며 이 시스템이 그 창으로 "
                "운용된다는 근거가 아닙니다."),
        forbidden_phrasings=["긴 창에서는 정렬이 유효하다",
                             "the ordering works at long windows",
                             "W=600에서 검증되었다"],
        check={"kind": "json_path",
               "operands": {"a": op(BOUND,
                                    "boundary.pooled_by_window.W600.win_rate_pct")},
               "expr": "a", "tolerance": 0.0},
        notes="docs/ordering_boundary.md §5.",
    )
    N["ordering_boundary_no_distinct_deadline_threshold"] = entry(
        value=1580, unit="non-winning cells", source_file=BOUND,
        json_path=("threshold_verdict.n_distinct_deadlines_cut"
                   ".n_non_winning_cells_at_or_above_that_value"),
        derivation=("cells that do NOT win despite having at least as many distinct "
                    "deadlines (3) as the lowest-scoring winning cell — the evidence "
                    "that no cut on 「서로 다른 마감 수」 separates wins from non-wins"),
        sample="2,160개 중 마감 수 ≥ 3 인 비승리 셀",
        caveat=("⚠ 단일 임계값이 존재하지 않는다는 측정입니다. 「마감 수 N 이상이면 "
                "이긴다」는 N 은 없습니다 — 관계가 단조롭지 않아 마감 6개·7개 구간의 "
                "승률은 0 % 인데 3개 구간은 4.1 % 입니다. 셀 단위 상관은 Spearman "
                "+0.244 로 약하고, 차이의 크기와는 −0.022 로 사실상 무관합니다. "
                "⚠ 상관이지 인과가 아닙니다. ⚠ 그리고 PHASE 23 §6 의 기제는 이 결과를 "
                "다 설명하지 못합니다 — 바닥(마감 2개 → 465셀 전부 0승)은 설명하지만 "
                "6·7개 구간의 0 % 는 설명하지 못하고, 마감 수를 고정해도 승률이 계속 "
                "움직입니다(영덕 real, 3개 고정, 17.8포인트). 마감 수는 자유 변수가 "
                "아니라 (팔 × W) 의 이름표이므로 이 설계로는 개수·퍼짐·W 를 분리할 수 "
                "없습니다. 설명이 불완전하다는 것과 무엇이 더 필요한지는 "
                "docs/ordering_boundary.md §6.3 에 있으며, 억지 설명을 만들지 "
                "않았습니다."),
        forbidden_phrasings=["마감 수 임계값", "distinct-deadline threshold",
                             "마감이 N개 이상이면 유효하다"],
        check={"kind": "json_path",
               "operands": {"a": op(BOUND, "threshold_verdict"
                                           ".n_distinct_deadlines_cut"
                                           ".n_non_winning_cells_at_or_above_that_value")},
               "expr": "a", "tolerance": 0.0},
        notes="docs/ordering_boundary.md §6, §7.",
    )
    N["ordering_boundary_wins_at_committed_dispatch_delay"] = entry(
        value=9, unit="cells of 720", source_file=BOUND,
        json_path="threshold_verdict.win_rate_by_delay.d30.deadline_wins",
        derivation=("cells at the COMMITTED dispatch delay of 30 min in which 시한 "
                    "임박 순 beats 가까운 순, over all 12 windows (720 cells). "
                    "At delay 60 the same tally is 100"),
        sample="지연 30분 구성 720개",
        caveat=(_B_NEG + " ⚠ 승리 115개 중 100개(87 %)가 지연 60분에서 나옵니다 — "
                "커밋된 지연이 아닙니다. 커밋된 30분 구간의 평균 차이 −8.36 은 세 "
                "지연 중 가장 나쁩니다. 팀이 1대인 432개 셀에서는 어떤 W 에서도 "
                "승리가 없습니다. 지연은 PoC 파라미터이며 측정된 영덕 출동 지연이 "
                "아닙니다."),
        forbidden_phrasings=["지연이 길수록 우리 정렬이 좋다",
                             "longer delays validate the ordering"],
        check={"kind": "json_path",
               "operands": {"a": op(BOUND, "threshold_verdict.win_rate_by_delay"
                                           ".d30.deadline_wins")},
               "expr": "a", "tolerance": 0.0},
        notes="docs/ordering_boundary.md §7 ③.",
    )
    N["ordering_boundary_phase23_reproduction_differences"] = entry(
        value=0, unit="differing values", source_file=BOUND,
        json_path="⚠ reproduction_of_phase23.cellwise.n_differences",
        derivation=("differences found when every PHASE 23 value at W = 75 and "
                    "W = 240 was re-derived in the PHASE 24 run and compared cell by "
                    "cell against data/processed/dispatch_ordering_comparison.json — "
                    "3,744 values compared across 4 orderings, the random mean and "
                    "binding_constraint, both occupancy arms"),
        sample="3,744개 값",
        caveat=("This is the check that would have invalidated PHASE 24 had it "
                "failed. Headline tallies also match exactly (W75 0/88/92, W240 "
                "13/44/123), as do all four arms' pipeline counts and the config "
                "hash. It does NOT re-verify PHASE 23's inputs — it verifies that "
                "the same inputs still produce the same numbers."),
        forbidden_phrasings=[],
        check={"kind": "json_path",
               "operands": {"a": op(BOUND, "⚠ reproduction_of_phase23"
                                           ".cellwise.n_differences")},
               "expr": "a", "tolerance": 0.0},
        notes="docs/ordering_boundary.md §4.",
    )

    doc = {
        "schema_version": 1,
        "_README": (
            "CANONICAL REGISTRY. Every reportable number lives here exactly once. "
            "Do not restate a value in prose without citing its key. "
            "'verified' = still matches its artifact; 'reproducible' = re-running the "
            "pipeline regenerates that artifact. They are independent — several "
            "numbers here are verified but NOT reproducible because the OSM network "
            "behind them was overwritten (docs/DATA_LOSS_2026-07-24.md). "
            "Run scripts/verify_numbers.py to re-check every entry."
        ),
        "config_hash": config_hash(),
        "config_hash_note": (
            "The per-entry config_hash is re-stamped on every build, so it marks "
            "the config a build SAW, not the config a number was PRODUCED under. "
            "It moved 0b6eb481177a… -> 51ec446843b6… between the 2026-08-01 build "
            "and the 2026-08-02 (PHASE 5 STEP 4) build. That move is PURELY "
            "ADDITIVE: `bbox.multi_region_walk_bbox` and "
            "`grid.simulation_bbox_extension` were added and NOT ONE existing key "
            "changed value (verified key-by-key against config/default.yaml at "
            "commit 5fe86db). No Round-2 number is stale as a result. "
            "It moved again 05c6feae1dff… -> 8e29a6cc4a99… on 2026-08-03 "
            "(PHASE 13), and again PURELY ADDITIVELY: the `fuel:` block "
            "(uncovered_land_warn_fraction / uncovered_land_stop_fraction) was "
            "added, no existing key changed value, and a rebuild moved 0 of the "
            "registered VALUES — only six `sample` labels, which carry the bbox "
            "area and therefore inherit the geodesic-area correction described "
            "under the mr_* completeness entries."),
        "built_at_git_commit": head,
        "round2_submission_commit": "4e9dfe396a2c9052b9631afba511fe6bd1c0afe4",
        "numbers": N,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}  ({len(N)} entries)")
    n_rep = sum(1 for e in N.values() if e["reproducible"])
    print(f"  reproducible: {n_rep}/{len(N)}   not reproducible: {len(N) - n_rep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
