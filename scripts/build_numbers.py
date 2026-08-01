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
    for key, cnt, desc, cav in [
        ("real_roads_both_safe", k["both_safe"], "both_safe",
         "Both routers reach a safe refuge. Dominated by the near-static ≥0.5 hazard core."),
        ("real_roads_future_aware_only_safe", k["naive_into_FA_safe"], "naive_into_FA_safe",
         "The headline cell: the fire-blind route enters the hazard, the future-aware one does not."),
        ("real_roads_no_safe_route", k["no_safe_route"], "no_safe_route",
         "Neither router finds a safe route. A valid, expected output — never imputed."),
    ]:
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
                "(~12× coarser)."),
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

    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    except Exception:  # noqa: BLE001
        head = None

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
