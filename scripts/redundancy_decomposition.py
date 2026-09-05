#!/usr/bin/env python
"""Is the Arm E null caused by redundancy? (Session 13 Phase 2)

``upslope_alignment`` correlates 0.243 with ``elev_above_source_m``, which
already carries a signed "is this cell above its source" signal. Permutation
importance splits credit between correlated features, so the rank-15 result
could be redundancy rather than absence of signal. This measures which.

FOUR configurations, so the comparison isolates the substitution instead of
confounding it with a change in column count:

    A18  = Arm A's 16                          (baseline, already computed)
    E18  = 16 + upslope_alignment + slope_forcing   (Arm E, already computed)
    A15  = 16 - elev_above_source_m            (15 columns)
    E17  = 15 + upslope_alignment + slope_forcing   (17 columns)
    N17  = 15 + two noise columns              (the MATCHED null for E17)

E17 must be read against A15, not against A18 — otherwise a column-count change
and a feature substitution are measured together. And per Session 13 Phase 1,
E17-vs-A15 needs its own noise envelope: the column-addition null is a property
of the feature set, not a constant, so the 18-column envelope cannot be assumed
to transfer.

    python scripts/redundancy_decomposition.py --run --draws 30
    python scripts/redundancy_decomposition.py --aggregate

Writes ONLY under data/processed/arms/redundancy/ and docs/.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

ROOT = REPO / "data" / "processed" / "arms" / "redundancy"
OUT = REPO / "docs" / "redundancy_decomposition.json"

DROPPED = "elev_above_source_m"
ESTIMATOR_SEED = 20250603
METRICS = ("pooled_auc", "mean_of_folds_auc", "mid_band_auc", "far_band_auc",
           "gentle_auc", "steep_auc")


def _lofo():
    spec = importlib.util.spec_from_file_location(
        "arm_e_lofo", REPO / "scripts" / "arm_e_lofo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def config_columns(tag: str, L) -> tuple[str, ...]:
    from wildfireguardian.spread_v2.features import FEATURE_COLUMNS
    from wildfireguardian.spread_v2_arme.features import ARM_E_FEATURE_COLUMNS

    base15 = tuple(c for c in FEATURE_COLUMNS if c != DROPPED)
    return {
        "A15": base15,
        "E17": base15 + ARM_E_FEATURE_COLUMNS,
        "N17": base15 + L.NOISE_COLUMNS,
    }[tag]


def metrics_from_folds(folds, L) -> dict:
    good = [f for f in folds if f.get("auc") is not None]
    y = np.concatenate([np.array(f["oof"]["label"]) for f in good])
    p = np.concatenate([np.array(f["oof"]["prob"]) for f in good])
    band = np.concatenate([np.array(f["oof"]["dist_band"]) for f in good])
    steep = np.concatenate([np.array(f["oof"]["steep"]) for f in good]).astype(bool)
    aucs = [f["auc"] for f in folds if f["auc"] is not None]
    return {
        "pooled_auc": L._safe_auc(y, p),
        "mean_of_folds_auc": float(np.mean(aucs)),
        "mid_band_auc": L._safe_auc(y[band == "mid"], p[band == "mid"]),
        "far_band_auc": L._safe_auc(y[band == "far"], p[band == "far"]),
        "gentle_auc": L._safe_auc(y[~steep], p[~steep]),
        "steep_auc": L._safe_auc(y[steep], p[steep]),
        "per_fire_auc": {f["fire"]: f["auc"] for f in folds},
    }


def run_config(tag: str, noise_seed: int | None = None) -> dict:
    L = _lofo()
    ds = L.load_dataset("A").copy()
    if noise_seed is not None:
        rng = np.random.default_rng(noise_seed)
        for c in L.NOISE_COLUMNS:
            ds[c] = rng.standard_normal(len(ds))
    cols = config_columns(tag, L)
    t0 = time.time()
    folds = [L.run_fold(ds, f, cols, ESTIMATOR_SEED)
             for f in sorted(ds["fire_id"].unique())]
    good = [f for f in folds if f.get("auc") is not None]
    out = metrics_from_folds(folds, L)
    out.update({
        "config": tag, "n_features": len(cols), "feature_columns": list(cols),
        "noise_seed": noise_seed, "seconds": round(time.time() - t0, 1),
        "importance_ranking": L._imp_table(good, cols),
    })
    return out


def aggregate() -> dict:
    L = _lofo()
    A18 = json.loads((REPO / "data/processed/arms/A_replication_e/lofo_arm_A.json")
                     .read_text(encoding="utf-8"))
    E18 = json.loads((REPO / "data/processed/arms/E/lofo_arm_E.json")
                     .read_text(encoding="utf-8"))
    A15 = json.loads((ROOT / "A15.json").read_text(encoding="utf-8"))
    E17 = json.loads((ROOT / "E17.json").read_text(encoding="utf-8"))
    draws = [json.loads(p.read_text(encoding="utf-8"))
             for p in sorted((ROOT / "N17").glob("seed_*.json"))]
    if len(draws) < 5:
        raise SystemExit(f"only {len(draws)} N17 draws — run more")

    def imp(obj, feat):
        r = next((x for x in obj["importance_ranking"] if x["feature"] == feat), None)
        return None if r is None else {
            "rank": r["rank"], "n_features": obj.get("n_features", 18),
            "weighted_mean_auc_drop": round(r["weighted_mean_auc_drop"], 6),
            "fold_sd": round(r["fold_sd"], 6) if r["fold_sd"] is not None else None}

    # E17 against A15, with the matched 17-column null.
    a15 = {m: A15[m] for m in METRICS}
    env, placed = {}, {}
    for m in METRICS:
        d = [x[m] - a15[m] for x in draws]
        e_d = E17[m] - a15[m]
        arr = np.asarray(d, float)
        env[m] = {"n_draws": len(d),
                  "null_mean_delta": round(float(arr.mean()), 6),
                  "null_sd_delta": round(float(arr.std(ddof=1)), 6),
                  "null_p5_delta": round(float(np.percentile(arr, 5)), 6),
                  "null_p95_delta": round(float(np.percentile(arr, 95)), 6)}
        placed[m] = {"E17_delta_vs_A15": round(float(e_d), 6),
                     "percentile_of_null": round(
                         float(100 * (arr <= e_d).mean()), 1),
                     "exceeds_p95": bool(e_d > np.percentile(arr, 95))}

    ua18, ua17 = imp(E18, "upslope_alignment"), imp(E17, "upslope_alignment")
    sf18, sf17 = imp(E18, "slope_forcing"), imp(E17, "slope_forcing")
    rise = ua17["weighted_mean_auc_drop"] - ua18["weighted_mean_auc_drop"]
    payload = {
        "schema_version": 1,
        "title": "Redundancy decomposition — is the Arm E null caused by "
                 f"overlap with {DROPPED}?",
        "provenance": "derived", "arm": "E_redundancy",
        "generated_by": "scripts/redundancy_decomposition.py",
        "dropped_feature": DROPPED,
        "correlation_upslope_alignment_with_dropped": 0.2426,
        "configs": {
            "A18": {"n_features": 18 - 2, **{m: A18[m] for m in
                    ("pooled_auc", "mean_of_folds_auc", "far_band_auc")}},
            "E18": {"n_features": 18, **{m: E18[m] for m in
                    ("pooled_auc", "mean_of_folds_auc", "far_band_auc")}},
            "A15": {"n_features": 15, **{m: A15[m] for m in
                    ("pooled_auc", "mean_of_folds_auc", "far_band_auc")}},
            "E17": {"n_features": 17, **{m: E17[m] for m in
                    ("pooled_auc", "mean_of_folds_auc", "far_band_auc")}},
        },
        "dropping_elev_above_source_costs": {
            m: round(A15[m] - A18[m], 6) for m in METRICS if m in A18},
        "upslope_alignment": {"in_E18": ua18, "in_E17": ua17,
                              "rise_when_dropped": round(rise, 6),
                              "rise_in_units_of_its_own_fold_sd": round(
                                  rise / ua18["fold_sd"], 3) if ua18["fold_sd"] else None},
        "slope_forcing": {"in_E18": sf18, "in_E17": sf17},
        "matched_null_17col": env,
        "E17_placed_in_matched_null": placed,
        "n_null_draws": len(draws),
        # The one metric Arm E exceeds the null on is mean-of-folds, and
        # mean-of-folds gives gangneung_2023 — 396 rows, 8 positive cells,
        # 0.26 % of the evidence — an equal sixth of the vote. Recomputing it
        # over the other five fires is the whole test of whether the exceedance
        # is a finding or a fold.
        "mean_of_folds_excluding_smallest_fold": {
            "excluded": "gangneung_2023",
            "E18_minus_A18_all6": round(
                E18["mean_of_folds_auc"] - A18["mean_of_folds_auc"], 6),
            "E18_minus_A18_five": round(float(np.mean(
                [E18["per_fire_auc"][f] - A18["per_fire_auc"][f]
                 for f in A15["per_fire_auc"] if f != "gangneung_2023"])), 6),
            "E17_minus_A15_all6": round(
                E17["mean_of_folds_auc"] - A15["mean_of_folds_auc"], 6),
            "E17_minus_A15_five": round(float(np.mean(
                [E17["per_fire_auc"][f] - A15["per_fire_auc"][f]
                 for f in A15["per_fire_auc"] if f != "gangneung_2023"])), 6),
        },
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    print(f"=== dropping {DROPPED} from Arm A costs ===")
    for m, v in payload["dropping_elev_above_source_costs"].items():
        print(f"  {m:20s} {v:+.5f}")
    print("\n=== upslope_alignment importance ===")
    print(f"  in E18 (18 cols): rank {ua18['rank']}  {ua18['weighted_mean_auc_drop']:+.5f}"
          f"  fold_sd {ua18['fold_sd']:.5f}")
    print(f"  in E17 (17 cols): rank {ua17['rank']}  {ua17['weighted_mean_auc_drop']:+.5f}"
          f"  fold_sd {ua17['fold_sd']:.5f}")
    print(f"  rise {rise:+.5f} = {payload['upslope_alignment']['rise_in_units_of_its_own_fold_sd']}"
          f" x its own fold sd")
    print(f"\n=== E17 vs A15, against the matched 17-column null ({len(draws)} draws) ===")
    for m in METRICS:
        e, n = placed[m], env[m]
        print(f"  {m:20s} d={e['E17_delta_vs_A15']:+.4f}  null {n['null_mean_delta']:+.4f}"
              f" ± {n['null_sd_delta']:.4f}  -> {e['percentile_of_null']:5.1f}th pct")
    print(f"wrote {OUT.relative_to(REPO)}")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--draws", type=int, default=30)
    ap.add_argument("--budget", type=float, default=140.0)
    ap.add_argument("--aggregate", action="store_true")
    args = ap.parse_args()

    if args.aggregate:
        aggregate()
        return 0
    if not args.run:
        ap.error("pass --run or --aggregate")

    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "N17").mkdir(exist_ok=True)
    t0 = time.time()
    for tag in ("A15", "E17"):
        dest = ROOT / f"{tag}.json"
        if dest.exists():
            print(f"cached {tag}")
            continue
        print(f"running {tag} ...", flush=True)
        r = run_config(tag)
        dest.write_text(json.dumps(r) + "\n", encoding="utf-8")
        print(f"  pooled={r['pooled_auc']:.4f} ({r['seconds']}s)", flush=True)

    for s in range(1, args.draws + 1):
        dest = ROOT / "N17" / f"seed_{s:03d}.json"
        if dest.exists():
            continue
        if time.time() - t0 > args.budget:
            n = sum(1 for _ in (ROOT / "N17").glob("seed_*.json"))
            print(f"budget reached; {n} of {args.draws} N17 draws — re-run to continue")
            return 0
        r = run_config("N17", noise_seed=s)
        dest.write_text(json.dumps(r) + "\n", encoding="utf-8")
        print(f"  N17 seed={s} pooled={r['pooled_auc']:.4f} ({r['seconds']}s)", flush=True)
    print("all configurations present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
