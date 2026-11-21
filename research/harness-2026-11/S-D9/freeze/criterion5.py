"""Stage-2 criterion 5 (A1 §6.1) read rule, as pinned in STAGE2_PINS.md (Iris, orchestrator 16:40Z).

Criterion 5: the candidate's lowest fixed bin [0, 0.1) in the 4 km band has an absolute
calibration gap no larger than that of EACH of persistence, dilation_8h and logistic_rebuilt.
Gap(m) = |observed frequency - mean prediction| over the cells model m puts in [0, 0.1).

Edge cases (pinned): an empty candidate bin -> NOT EVALUABLE, counted as not met; an empty
reference bin imposes no bound; all three reference bins empty -> NOT EVALUABLE, not met.

Descriptive only (no criterion role; orchestrator 16:40Z): the bin count beside each gap and
a whole-fire bootstrap 95% interval of Gap(cand) - Gap(ref), using the sd9bench resampling
convention (default_rng(20261030).integers(0, n_fires, (10000, n_fires))).

The VERDICT is decided on the table's own numbers: the score_criteria.py output
(--scores), cumulative_bands["4000"]...calibration[0]. This script's recomputation from
the entries is a CHECK only: counts must match exactly, and gaps within an absolute 1e-12
(float summation order differs, by about 1e-14). Any disagreement beyond that raises
and stops the report. Note for readers: each model's lowest bin holds
different cells, so this is not a like-for-like cell comparison.

Usage (research/harness-2026-11/S-D9 on PYTHONPATH):
  python freeze/criterion5.py --scores SCORES.json --candidate NAME --out C5.json FIRE.npz ...
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from sd9bench import load

REFERENCES = ("persistence", "dilation_8h", "logistic_rebuilt")
BAND_M = 4000.0
UPPER = 0.1
DRAWS = 10000
SEED = 20261030
POPULATION = "full_rectangle"


def _sums(fire_index, n_fires, p, y):
    """Per-fire count, sum of p and sum of y over the cells with p in [0, 0.1)."""
    inbin = p < UPPER
    count = np.bincount(fire_index, weights=inbin.astype(float), minlength=n_fires)
    sp = np.bincount(fire_index, weights=np.where(inbin, p, 0.0), minlength=n_fires)
    sy = np.bincount(fire_index, weights=np.where(inbin, y, 0.0), minlength=n_fires)
    return count, sp, sy


def _gap(count, sp, sy):
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, np.abs(sy / count - sp / count), np.nan)


GAP_ABS_TOL = 1e-12


class CheckError(RuntimeError):
    pass


def table_gaps(scores: dict, names) -> dict:
    """Count and gap per model from the score_criteria.py table (these decide the verdict)."""
    models = scores["cumulative_bands"]["4000"]["models"]
    out = {}
    for m in names:
        b = models[m]["pooled"]["calibration"][0]
        if b["lower"] != 0.0 or abs(b["upper"] - UPPER) > 1e-12:
            raise CheckError(f"unexpected lowest bin for {m}: {b['lower']}..{b['upper']}")
        c = int(b["count"])
        out[m] = dict(count=c, gap=None if c == 0 else float(abs(b["observed_frequency"] - b["mean_prediction"])))
    return out


def evaluate(entries, candidate: str, table: dict, draws: int = DRAWS, seed: int = SEED) -> dict:
    band = entries.dist_m <= BAND_M
    fires, fire_index = np.unique(entries.fire[band], return_inverse=True)
    y = entries.y[band].astype(float)
    n = len(fires)
    sampled = np.random.default_rng(seed).integers(0, n, size=(draws, n))
    per_model, boot = {}, {}
    for m in (candidate,) + REFERENCES:
        c, sp, sy = _sums(fire_index, n, entries.predictions[m][band].astype(float), y)
        tc, tp, ty = c.sum(), sp.sum(), sy.sum()
        own = dict(count=int(tc), gap=None if tc == 0 else float(abs(ty / tc - tp / tc)))
        tab = table[m]
        if own["count"] != tab["count"]:
            raise CheckError(f"{m}: bin count {own['count']} != table {tab['count']}")
        if (own["gap"] is None) != (tab["gap"] is None) or (
                own["gap"] is not None and abs(own["gap"] - tab["gap"]) > GAP_ABS_TOL):
            raise CheckError(f"{m}: recomputed gap {own['gap']} vs table {tab['gap']} beyond {GAP_ABS_TOL}")
        per_model[m] = dict(count=tab["count"], gap=tab["gap"], recomputed_gap=own["gap"])
        boot[m] = _gap(c[sampled].sum(axis=1), sp[sampled].sum(axis=1), sy[sampled].sum(axis=1))
    cand = per_model[candidate]
    comparisons, bounds = {}, []
    for r in REFERENCES:
        ref = per_model[r]
        d = boot[candidate] - boot[r]
        ok = d[~np.isnan(d)]
        interval = None if len(ok) == 0 else [float(x) for x in np.quantile(ok, [0.025, 0.975])]
        passes = None if (cand["gap"] is None or ref["gap"] is None) else bool(cand["gap"] <= ref["gap"])
        if ref["gap"] is not None:
            bounds.append(passes)
        comparisons[r] = dict(reference_gap=ref["gap"], reference_count=ref["count"], candidate_not_larger=passes,
                              descriptive_bootstrap_95_interval_of_gap_difference=interval,
                              bootstrap_draws_undefined=int(np.isnan(d).sum()))
    if cand["gap"] is None:
        verdict = "NOT EVALUABLE (empty candidate bin): not met"
    elif not bounds:
        verdict = "NOT EVALUABLE (all reference bins empty): not met"
    else:
        verdict = "met" if all(bounds) else "not met"
    return dict(criterion=5, candidate=candidate, band_m=BAND_M, bin=[0.0, UPPER], verdict=verdict,
                met=verdict == "met", per_model=per_model, comparisons=comparisons, draws=draws, seed=seed,
                verdict_source="score_criteria table (cumulative_bands 4000, calibration[0]); recomputation is a check only",
                note="each model's lowest bin holds different cells; descriptive intervals have no criterion role")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="criterion5")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--scores", required=True, type=Path)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    entries = load(args.files, None, population=POPULATION)
    if entries.dist_m is None:
        raise SystemExit("dist_m is required for the 4 km band")
    table = table_gaps(json.loads(args.scores.read_text()), (args.candidate,) + REFERENCES)
    result = evaluate(entries, args.candidate, table)
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True, allow_nan=False) + "\n")
    print(f"criterion 5 for {args.candidate}: {result['verdict']}")


if __name__ == "__main__":
    main()
