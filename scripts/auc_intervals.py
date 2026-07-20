#!/usr/bin/env python
"""Confidence intervals + significance for the spread_v2 LOFO AUC (priority 2).

Re-runs the **canonical** leave-one-fire-out model (seed 20250603, the 16
`FEATURE_COLUMNS`, the same fold set) ONCE to persist the per-fold out-of-fold
predictions (which are not currently stored), **gates** them against the canonical
numbers (pooled 0.867 / mean-of-folds 0.90 / the per-fire AUCs), and only then
reports:

  * per-fire ROC-AUC with **DeLong 95 % CIs** (each fold has thousands of cells →
    well-powered) and a **DeLong significance test vs AUC = 0.5** (the test
    hypothesis H1 needs) + a label-permutation cross-check;
  * the **mean-of-folds** interval WITH the explicit n=6 small-sample caveat;
  * a **pooled bootstrap CI**, labelled pooled (NOT the generalization figure);
  * the deferred **far-band (>3 km) mean-of-folds** AUC next to the pooled 0.877.

NO model change, NO retuning, NO feature change — this only re-runs the canonical
model to save outputs and compute inference on them.

*** Consistency gate ***  If the re-run does NOT reproduce the canonical AUCs
within rounding, the script STOPs (exit 3) and reports — it never "fixes" the
model. If the (git-ignored) FIRMS/ERA5/DEM bundle is absent it cannot run at all
and STOPs (exit 2) without fabricating any number.

Run:  python scripts/auc_intervals.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

PROC = REPO / "data" / "processed"

# Canonical Build-B numbers to gate against (data/processed/spread_v2_lofo.json,
# six-fire run, seed 20250603).
CANON_POOLED = 0.8666547831321919
CANON_MEAN_OF_FOLDS = 0.901        # mean of the six per_fire_auc values
CANON_PER_FIRE = {
    "gangneung_2023": 0.9329710144927537,
    "hongseong_2023": 0.9556098964326812,
    "miryang_2022": 0.9814412850010852,
    "uiseong_andong_2025": 0.8594557270306507,
    "uljin_samcheok_2022": 0.8946649818524703,
    "yeongdeok_2025": 0.7827540499481829,
}
CANON_FAR_BAND_POOLED = 0.8205213474141444
GATE_TOL = 1e-3            # rounding tolerance for the consistency gate
FAR_BAND_MIN_M = 3000.0    # ">3 km" far band (the far-field reach question)


def _blocked(reason: str) -> int:
    print("=" * 78, file=sys.stderr)
    print("STOP (exit 2): cannot re-run LOFO — consistency gate NOT attempted.",
          file=sys.stderr)
    print(reason, file=sys.stderr)
    print("\nThis script needs the raw FIRMS/ERA5/DEM bundle to rebuild the LOFO\n"
          "dataset (it is git-ignored and absent in a fresh clone). Provide it via\n"
          "  unzip firms_data.zip -d data/raw/        # -> data/raw/firms/...\n"
          "or set $WFG_FIRMS_DIR, then re-run. No numbers are reported without it\n"
          "(reporting CIs without the data would be fabrication).", file=sys.stderr)
    print("=" * 78, file=sys.stderr)
    return 2


def _gate(label: str, got: float, want: float, tol: float = GATE_TOL) -> bool:
    ok = got is not None and abs(got - want) <= tol
    flag = "OK " if ok else "MISMATCH"
    print(f"  [gate {flag}] {label}: re-run {got!r} vs canonical {want!r} "
          f"(|Δ|={'n/a' if got is None else f'{abs(got-want):.2e}'}, tol {tol})")
    return ok


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=20250603)
    ap.add_argument("--hazard-cell-m", type=float, default=500.0)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--n-perm", type=int, default=1000)
    ap.add_argument("--out", default=str(PROC / "auc_intervals.json"))
    ap.add_argument("--save-oof", default=str(PROC / "spread_v2_lofo_oof.parquet"))
    args = ap.parse_args()

    from wildfireguardian.spread_v2 import data, features
    from wildfireguardian.spread_v2.model import DEFAULT_SEED, leave_one_fire_out
    from wildfireguardian.validation.auc_stats import (
        bootstrap_auc_ci,
        delong_ci,
        delong_significance,
        mean_of_folds_interval,
        permutation_test_auc,
    )

    if not data.data_available():
        return _blocked("data.data_available() == False (no FIRMS bundle / $WFG_FIRMS_DIR).")
    if args.seed != DEFAULT_SEED:
        print(f"WARNING: seed {args.seed} != canonical {DEFAULT_SEED}; the gate uses "
              f"the canonical numbers and will (correctly) fail.", file=sys.stderr)

    # ---- 1. re-run the canonical LOFO, persist the per-fold predictions ----
    print("[1/4] rebuilding LOFO dataset + re-running canonical model (no change) ...")
    fire_ids = [m.id for m in data.list_fires()]
    ds = features.build_dataset(fire_ids, cell_size_m=args.hazard_cell_m, buffer_m=6000.0)
    lofo = leave_one_fire_out(ds, seed=args.seed, compute_importance=False)
    oof = lofo.oof.copy()
    # distance band from dist_to_fire_m so ">3 km" is unambiguous per fire.
    oof["far_band"] = oof["dist_to_fire_m"].to_numpy() > FAR_BAND_MIN_M
    Path(args.save_oof).parent.mkdir(parents=True, exist_ok=True)
    try:
        oof.to_parquet(args.save_oof)
        oof_artifact = args.save_oof
    except Exception:  # parquet engine optional — fall back to gzip csv
        oof_artifact = args.save_oof.replace(".parquet", ".csv.gz")
        oof.to_csv(oof_artifact, index=False, compression="gzip")
    print(f"      persisted {len(oof)} per-fold predictions -> {oof_artifact}")

    # ---- 2. consistency gate (STOP on mismatch) ----
    print("[2/4] consistency gate vs the canonical numbers ...")
    per_fire_rerun = {f: lofo.per_fire_auc.get(f) for f in CANON_PER_FIRE}
    mof_rerun = float(np.mean([v for v in per_fire_rerun.values() if v is not None]))
    gate_ok = _gate("pooled AUC", lofo.pooled_auc, CANON_POOLED)
    gate_ok &= _gate("mean-of-folds", round(mof_rerun, 3), CANON_MEAN_OF_FOLDS, tol=2e-3)
    for f, want in CANON_PER_FIRE.items():
        gate_ok &= _gate(f"per-fire {f}", per_fire_rerun.get(f), want)
    if not gate_ok:
        print("\nSTOP (exit 3): re-run did NOT reproduce the canonical AUCs — not "
              "proceeding, not 'fixing' the model. Investigate the data/seed/fold set.",
              file=sys.stderr)
        return 3
    print("      gate PASSED — proceeding to intervals + significance.")

    # ---- 3. intervals + significance ----
    print("[3/4] per-fire DeLong CIs + significance vs 0.5; pooled bootstrap; far-band ...")
    per_fire = {}
    for fid, grp in oof.groupby("fire_id"):
        y, p = grp["label"].to_numpy(), grp["prob"].to_numpy()
        rec = {"auc_ci_delong": delong_ci(y, p).as_dict(),
               "significance_vs_0p5": delong_significance(y, p, ref=0.5),
               "permutation_vs_0p5": permutation_test_auc(y, p, n_perm=args.n_perm,
                                                          seed=args.seed)}
        far = grp[grp["far_band"]]
        if far["label"].nunique() == 2:
            rec["far_band_auc_ci_delong"] = delong_ci(far["label"].to_numpy(),
                                                      far["prob"].to_numpy()).as_dict()
        per_fire[fid] = rec

    per_fire_auc_list = [per_fire[f]["auc_ci_delong"]["auc"] for f in per_fire]
    mof = mean_of_folds_interval(per_fire_auc_list)
    pooled_boot = bootstrap_auc_ci(oof["label"].to_numpy(), oof["prob"].to_numpy(),
                                   n_boot=args.n_boot, seed=args.seed)
    far_all = oof[oof["far_band"]]
    far_per_fire = [delong_ci(g["label"].to_numpy(), g["prob"].to_numpy()).auc
                    for _f, g in far_all.groupby("fire_id") if g["label"].nunique() == 2]
    far_mof = mean_of_folds_interval(far_per_fire)
    far_pooled = bootstrap_auc_ci(far_all["label"].to_numpy(), far_all["prob"].to_numpy(),
                                  n_boot=args.n_boot, seed=args.seed)

    # ---- 4. report + save ----
    print("[4/4] per-fire AUC [95% CI] / p(vs 0.5):")
    for fid, rec in sorted(per_fire.items(), key=lambda kv: -kv[1]["auc_ci_delong"]["auc"]):
        ci = rec["auc_ci_delong"]
        p = rec["significance_vs_0p5"]["p_value"]
        sig = "significant" if p < 0.05 else "NOT significant"
        print(f"    {fid:<22} {ci['auc']:.3f}  [{ci['ci95'][0]:.3f}, {ci['ci95'][1]:.3f}]"
              f"  p={p:.2e}  ({sig}; n_pos={ci['n_pos']})")
    print(f"  mean-of-folds: {mof['mean']:.3f} ± {mof['sd']:.3f}  "
          f"95% CI [{mof['ci95'][0]:.3f}, {mof['ci95'][1]:.3f}]  (n={mof['n']}; "
          f"SMALL-SAMPLE — per-fold DeLong CIs are stronger)")
    print(f"  pooled (bootstrap, labelled pooled): {pooled_boot['auc']:.3f}  "
          f"95% CI [{pooled_boot['ci95'][0]:.3f}, {pooled_boot['ci95'][1]:.3f}]")
    print(f"  far-band (>3km) mean-of-folds: {far_mof['mean']:.3f} ± {far_mof['sd']:.3f} "
          f"(n={far_mof['n']}) vs pooled far-band {far_pooled['auc']:.3f} "
          f"[{far_pooled['ci95'][0]:.3f}, {far_pooled['ci95'][1]:.3f}] "
          f"(canonical pooled far-band {CANON_FAR_BAND_POOLED:.3f})")

    out = {
        "seed": args.seed, "gate_passed": True,
        "consistency_gate": {"pooled_canonical": CANON_POOLED,
                             "pooled_rerun": lofo.pooled_auc,
                             "mean_of_folds_canonical": CANON_MEAN_OF_FOLDS,
                             "mean_of_folds_rerun": round(mof_rerun, 4)},
        "per_fire": per_fire,
        "mean_of_folds_interval": mof,
        "pooled_bootstrap_ci": pooled_boot,
        "far_band_gt3km": {"mean_of_folds": far_mof, "pooled_bootstrap_ci": far_pooled,
                           "canonical_pooled": CANON_FAR_BAND_POOLED},
        "oof_artifact": oof_artifact,
        "method_notes": {
            "delong": "Sun & Xu 2014 fast midrank single-classifier variance; logit CI",
            "bootstrap": f"{args.n_boot} stratified resamples, seed {args.seed}",
            "permutation": f"{args.n_perm} label permutations, seed {args.seed}",
            "mean_of_folds": "t-interval; n=6 small-sample caveat carried",
            "no_model_change": True,
        },
    }
    Path(args.out).write_text(json.dumps(out, indent=2, default=str))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
