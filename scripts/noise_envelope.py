#!/usr/bin/env python
"""The column-addition null distribution (Session 13 Phase 1).

Session 12 added two columns of noise beside Arm A's sixteen and found the
pooled AUC moved +0.0082 — more than Arm E's two real slope features moved it.
That was ONE draw. One draw says "noise beat it once"; it does not say where
Arm E sits in the null. This script draws the null properly.

Each seed repeats the whole Arm A protocol — same 6 fires, same folds, same
hyperparameters, same seed 20250603 for the ESTIMATOR — changing only the
random numbers in the two added columns. The spread of the resulting deltas is
the column-addition floor, and Arm E's observed delta can then be quoted as a
percentile of it rather than as a comparison to a single sample.

⚠ The estimator seed is held FIXED at 20250603 across every draw. Only the
noise content varies. Letting both vary would fold estimator jitter into the
column-addition envelope and measure two things at once.

Per-seed results are cached, because one draw is a full 6-fold LOFO and this
environment kills any single command at ~178 s.

    python scripts/noise_envelope.py --run --seeds 20     # fills in what is missing
    python scripts/noise_envelope.py --aggregate

Writes ONLY under data/processed/arms/N_noise_control/ and docs/.
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

ARM_ROOT = REPO / "data" / "processed" / "arms"
ENVDIR = ARM_ROOT / "N_noise_control" / "envelope"
OUT = REPO / "docs" / "column_addition_envelope.json"

#: The estimator seed. Fixed for every draw — see the module docstring.
ESTIMATOR_SEED = 20250603

METRICS = ("pooled_auc", "mean_of_folds_auc", "mid_band_auc", "far_band_auc",
           "gentle_auc", "steep_auc")


def _lofo():
    spec = importlib.util.spec_from_file_location(
        "arm_e_lofo", REPO / "scripts" / "arm_e_lofo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_seed(noise_seed: int) -> dict:
    """One draw: 6 folds, two noise columns, every metric Arm E reports."""
    L = _lofo()
    from wildfireguardian.spread_v2.features import FEATURE_COLUMNS

    ds = L.load_dataset("A").copy()
    rng = np.random.default_rng(noise_seed)
    for c in L.NOISE_COLUMNS:
        ds[c] = rng.standard_normal(len(ds))
    cols = tuple(FEATURE_COLUMNS) + L.NOISE_COLUMNS

    t0 = time.time()
    folds = [L.run_fold(ds, f, cols, ESTIMATOR_SEED)
             for f in sorted(ds["fire_id"].unique())]
    good = [f for f in folds if f.get("auc") is not None]

    y = np.concatenate([np.array(f["oof"]["label"]) for f in good])
    p = np.concatenate([np.array(f["oof"]["prob"]) for f in good])
    band = np.concatenate([np.array(f["oof"]["dist_band"]) for f in good])
    steep = np.concatenate([np.array(f["oof"]["steep"]) for f in good]).astype(bool)
    aucs = [f["auc"] for f in folds if f["auc"] is not None]

    imp = L._imp_table(good, cols)
    noise_rows = [r for r in imp if r["feature"] in L.NOISE_COLUMNS]

    return {
        "noise_seed": noise_seed,
        "estimator_seed": ESTIMATOR_SEED,
        "seconds": round(time.time() - t0, 1),
        "pooled_auc": L._safe_auc(y, p),
        "mean_of_folds_auc": float(np.mean(aucs)),
        "mid_band_auc": L._safe_auc(y[band == "mid"], p[band == "mid"]),
        "far_band_auc": L._safe_auc(y[band == "far"], p[band == "far"]),
        "gentle_auc": L._safe_auc(y[~steep], p[~steep]),
        "steep_auc": L._safe_auc(y[steep], p[steep]),
        "per_fire_auc": {f["fire"]: f["auc"] for f in folds},
        "noise_importance": [
            {"feature": r["feature"], "rank": r["rank"],
             "weighted_mean_auc_drop": r["weighted_mean_auc_drop"],
             "fold_sd": r["fold_sd"]} for r in noise_rows],
        "n_features": len(cols),
    }


def percentile_of(value: float, sample: list[float]) -> float:
    """Share of the null at or below ``value``, in percent."""
    a = np.asarray(sample, dtype=float)
    return float(100.0 * (a <= value).mean())


def aggregate() -> dict:
    L = _lofo()
    A = json.loads((ARM_ROOT / "A_replication_e" / "lofo_arm_A.json")
                   .read_text(encoding="utf-8"))
    E = json.loads((ARM_ROOT / "E" / "lofo_arm_E.json").read_text(encoding="utf-8"))

    base = {
        "pooled_auc": A["pooled_auc"], "mean_of_folds_auc": A["mean_of_folds_auc"],
        "mid_band_auc": A["mid_band_auc"], "far_band_auc": A["far_band_auc"],
        "gentle_auc": A["stratified"]["gentle"]["pooled_auc"],
        "steep_auc": A["stratified"]["steep"]["pooled_auc"],
    }
    arm_e = {
        "pooled_auc": E["pooled_auc"], "mean_of_folds_auc": E["mean_of_folds_auc"],
        "mid_band_auc": E["mid_band_auc"], "far_band_auc": E["far_band_auc"],
        "gentle_auc": E["stratified"]["gentle"]["pooled_auc"],
        "steep_auc": E["stratified"]["steep"]["pooled_auc"],
    }

    draws = [json.loads(p.read_text(encoding="utf-8"))
             for p in sorted(ENVDIR.glob("seed_*.json"))]
    if len(draws) < 5:
        raise SystemExit(f"only {len(draws)} draws — run more before aggregating")

    envelope = {}
    for m in METRICS:
        d = [x[m] - base[m] for x in draws if x.get(m) is not None]
        e_delta = arm_e[m] - base[m]
        arr = np.asarray(d, dtype=float)
        envelope[m] = {
            "arm_A_replication": base[m],
            "n_draws": len(d),
            "null_mean_delta": round(float(arr.mean()), 6),
            "null_sd_delta": round(float(arr.std(ddof=1)), 6),
            "null_p5_delta": round(float(np.percentile(arr, 5)), 6),
            "null_p50_delta": round(float(np.percentile(arr, 50)), 6),
            "null_p95_delta": round(float(np.percentile(arr, 95)), 6),
            "null_min_delta": round(float(arr.min()), 6),
            "null_max_delta": round(float(arr.max()), 6),
            "arm_E_delta": round(float(e_delta), 6),
            "arm_E_percentile_of_null": round(percentile_of(e_delta, d), 1),
            "arm_E_exceeds_null_p95": bool(e_delta > np.percentile(arr, 95)),
        }

    ranks = [r["rank"] for x in draws for r in x["noise_importance"]]
    mags = [r["weighted_mean_auc_drop"] for x in draws for r in x["noise_importance"]]
    ua = next(r for r in E["importance_ranking"] if r["feature"] == "upslope_alignment")
    sf = next(r for r in E["importance_ranking"] if r["feature"] == "slope_forcing")

    imp_env = {
        "n_noise_columns_observed": len(mags),
        "rank_min": int(min(ranks)), "rank_median": float(np.median(ranks)),
        "rank_max": int(max(ranks)),
        "magnitude_mean": round(float(np.mean(mags)), 6),
        "magnitude_sd": round(float(np.std(mags, ddof=1)), 6),
        "magnitude_p5": round(float(np.percentile(mags, 5)), 6),
        "magnitude_p95": round(float(np.percentile(mags, 95)), 6),
        "upslope_alignment": {
            "rank": ua["rank"], "magnitude": round(ua["weighted_mean_auc_drop"], 6),
            "fold_sd": round(ua["fold_sd"], 6),
            "percentile_of_noise_magnitudes": round(
                percentile_of(ua["weighted_mean_auc_drop"], mags), 1)},
        "slope_forcing": {
            "rank": sf["rank"], "magnitude": round(sf["weighted_mean_auc_drop"], 6),
            "fold_sd": round(sf["fold_sd"], 6),
            "percentile_of_noise_magnitudes": round(
                percentile_of(sf["weighted_mean_auc_drop"], mags), 1)},
    }

    payload = {
        "schema_version": 1,
        "title": "Column-addition null envelope — what adding two columns does on its own",
        "provenance": "derived",
        "arm": "N_control",
        "generated_by": "scripts/noise_envelope.py",
        "what_this_is": (
            "The distribution of the change in every reported metric when TWO "
            "columns of pure noise are added to Arm A's sixteen. It is the floor "
            "an arm that changes the feature count must clear, and it is separate "
            "from — and on far-band larger than — the platform replication floor "
            "measured in Session 10 (docs/platform_drift.json)."),
        "protocol": ("6-fire LOGO-CV, HistGradientBoostingClassifier, spread_v2 "
                     "hyperparameters unchanged, estimator seed fixed at "
                     f"{ESTIMATOR_SEED}; only the noise content varies per draw."),
        "n_draws": len(draws),
        "noise_seeds": [x["noise_seed"] for x in draws],
        "seconds_per_draw_mean": round(
            float(np.mean([x["seconds"] for x in draws])), 1),
        "platform_floor_for_comparison": {
            "pooled_auc": 0.0064, "far_band_auc": 0.0307,
            "source": "docs/platform_drift.json"},
        "metrics": envelope,
        "noise_importance_envelope": imp_env,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    print(f"=== column-addition envelope, {len(draws)} draws ===")
    print(f"{'metric':20s} {'null mean':>10} {'sd':>9} {'p5':>9} {'p95':>9} "
          f"{'ArmE d':>9} {'pct':>6}")
    for m in METRICS:
        v = envelope[m]
        print(f"{m:20s} {v['null_mean_delta']:+10.4f} {v['null_sd_delta']:9.4f} "
              f"{v['null_p5_delta']:+9.4f} {v['null_p95_delta']:+9.4f} "
              f"{v['arm_E_delta']:+9.4f} {v['arm_E_percentile_of_null']:5.1f}%")
    print(f"\nnoise importance: rank {imp_env['rank_min']}-{imp_env['rank_max']} "
          f"(median {imp_env['rank_median']}), magnitude "
          f"{imp_env['magnitude_mean']:.5f} ± {imp_env['magnitude_sd']:.5f}")
    print(f"  upslope_alignment rank {imp_env['upslope_alignment']['rank']} "
          f"mag {imp_env['upslope_alignment']['magnitude']:.5f} -> "
          f"{imp_env['upslope_alignment']['percentile_of_noise_magnitudes']}th pct of noise")
    print(f"  slope_forcing     rank {imp_env['slope_forcing']['rank']} "
          f"mag {imp_env['slope_forcing']['magnitude']:.5f} -> "
          f"{imp_env['slope_forcing']['percentile_of_noise_magnitudes']}th pct of noise")
    print(f"wrote {OUT.relative_to(REPO)}")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--budget", type=float, default=150.0,
                    help="stop starting new draws after this many seconds")
    ap.add_argument("--aggregate", action="store_true")
    args = ap.parse_args()

    if args.aggregate:
        aggregate()
        return 0
    if not args.run:
        ap.error("pass --run or --aggregate")

    ENVDIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for s in range(1, args.seeds + 1):
        dest = ENVDIR / f"seed_{s:03d}.json"
        if dest.exists():
            continue
        if time.time() - t0 > args.budget:
            print(f"budget reached; {sum(1 for _ in ENVDIR.glob('seed_*.json'))} "
                  f"of {args.seeds} draws done — re-run to continue")
            return 0
        print(f"draw seed={s} ...", flush=True)
        res = run_seed(s)
        dest.write_text(json.dumps(res) + "\n", encoding="utf-8")
        print(f"  pooled={res['pooled_auc']:.4f} far={res['far_band_auc']:.4f} "
              f"({res['seconds']}s)", flush=True)
    print(f"all {args.seeds} draws present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
