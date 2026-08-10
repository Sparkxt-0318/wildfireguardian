#!/usr/bin/env python
"""Confidence intervals + significance for the spread_v2 LOFO AUC (priority 2).

Re-runs the **canonical** leave-one-fire-out model (seed 20250603, the 16
`FEATURE_COLUMNS`, the same fold set) ONCE to persist the per-fold out-of-fold
predictions (which are not currently stored), **gates** them against the canonical
numbers (pooled 0.905 / mean-of-folds 0.890 / the per-fire AUCs), and only then
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

# Canonical Build-B numbers to gate against (data/processed/spread_v2_lofo.json).
CANON_POOLED = 0.9053277489374548
CANON_MEAN_OF_FOLDS = 0.890
CANON_PER_FIRE = {
    "gangneung_2023": 0.6820231958762887,
    "hongseong_2023": 0.9448983570529749,
    "miryang_2022": 0.973692264885921,
    "uiseong_andong_2025": 0.8776874123436931,
    "uljin_samcheok_2022": 0.9180778687255129,
    "yeongdeok_2025": 0.9407755935389225,
}
CANON_FAR_BAND_POOLED = 0.8765583120330634
GATE_TOL = 1e-3            # rounding tolerance for the consistency gate
FAR_BAND_MIN_M = 3000.0    # ">3 km" far band (the far-field reach question)

#: ⚠ TWO LINEAGES CAN LEGITIMATELY PASS THE GATE, and the artifact records
#: which one did. The committed numbers above were measured on the
#: pre-correction DEM bundle; the 2026-08-02 re-acquisition installed the
#: CORRECTED rasters into data/raw, so a re-run on this machine's bundle
#: lands on the values committed in spread_v2_lofo_dem_corrected.json
#: (pooled 0.9036, gangneung fold +0.036) and the committed-only gate would
#: refuse a perfectly healthy bundle. The corrected values are READ FROM the
#: committed artifact, never typed here; anything matching NEITHER lineage
#: is real drift and still stops the run.
DEM_CORRECTED_JSON = PROC / "spread_v2_lofo_dem_corrected.json"


def _gate_lineages() -> list[tuple[str, float, dict[str, float]]]:
    """(label, pooled, per_fire) for each lineage this bundle may be."""
    lineages: list[tuple[str, float, dict[str, float]]] = [
        ("committed", CANON_POOLED, CANON_PER_FIRE)]
    try:
        d = json.loads(DEM_CORRECTED_JSON.read_text(encoding="utf-8"))
        lineages.append(("dem_corrected", float(d["pooled_auc"]),
                         {k: float(v) for k, v in d["per_fire_auc"].items()}))
    except (OSError, KeyError, ValueError):
        pass                       # gate falls back to committed-only
    return lineages


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

    # ---- 2. consistency gate (STOP on mismatch with EVERY known lineage) ----
    print("[2/4] consistency gate vs the known lineages ...")
    per_fire_rerun = {f: lofo.per_fire_auc.get(f) for f in CANON_PER_FIRE}
    mof_rerun = float(np.mean([v for v in per_fire_rerun.values() if v is not None]))
    gate_lineage: str | None = None
    for label, pooled_want, per_fire_want in _gate_lineages():
        print(f"      lineage {label!r}:")
        ok = _gate("pooled AUC", lofo.pooled_auc, pooled_want)
        mof_want = round(float(np.mean(list(per_fire_want.values()))), 3)
        ok &= _gate("mean-of-folds", round(mof_rerun, 3), mof_want, tol=2e-3)
        for f, want in per_fire_want.items():
            ok &= _gate(f"per-fire {f}", per_fire_rerun.get(f), want)
        if ok:
            gate_lineage = label
            break
    if gate_lineage is None:
        print("\nSTOP (exit 3): re-run reproduced NEITHER the committed nor the "
              "dem_corrected lineage — not proceeding, not 'fixing' the model. "
              "Investigate the data/seed/fold set.", file=sys.stderr)
        return 3
    print(f"      gate PASSED against the {gate_lineage!r} lineage — "
          "proceeding to intervals + significance.")

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
        # ⚠ Which lineage this run's bundle matched. "dem_corrected" means the
        # rasters are the 2026-08-02 re-acquisition and every interval below
        # is a corrected-lineage quantity — quote beside committed numbers
        # only with that label (docs/MODEL_CARD.md, DEM-correction section).
        "gate_lineage": gate_lineage,
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
