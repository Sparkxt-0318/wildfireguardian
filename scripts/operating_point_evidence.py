#!/usr/bin/env python
"""WFG-019 — the operating point, per fire, and why no threshold guarantee exists.

The project reports ROC-AUC 0.905 pooled / 0.890 mean-of-folds and, since Session
18, a recall of 0.138 at the operating threshold 0.3. Both are true and a judge
will ask how they can be. This script answers the question at the level the
answer actually lives at — **per fire** — and then tests whether the threshold
could be *calibrated* to carry a false-negative-rate guarantee.

NO MODEL IS FITTED HERE, and nothing is retrained. Every probability is read
from the committed leave-one-fire-out out-of-fold file
``data/processed/spread_v2_lofo_oof_cells.csv.gz`` (151,904 rows, 2,989
positives, six folds, seed 20250603), the same file
``scripts/oof_metrics.py`` scored. Refitting to add a column would mean these
numbers came from a different run than the AUC they sit beside.

    python scripts/operating_point_evidence.py            # write the artifact
    python scripts/operating_point_evidence.py --figure   # + the PR-curve panel

TWO THRESHOLDS, TWO SURFACES, ONE EASY MISREADING.
``config/default.yaml`` carries two probability cuts and they are not the same
knob:

* ``time.forward_sim_advance_threshold = 0.3`` is applied **per simulation
  step** to a per-step ignition probability. It is what the forward simulation
  uses to decide that a cell has been reached, and it is the threshold these
  recall numbers are computed at.
* ``pedestrian.walk_cutoff_p = 0.5`` (``p_cut``) is applied by the router to
  the **cumulative, survival-accumulated hazard field** — a different quantity
  on a different surface, at a different value.

So the recall reported here is *not* the routing field's miss rate, and a
sentence that treats it as one is wrong in both directions. The recall bounds
how quickly the simulated hazard *extent* grows; the router then reads the
accumulated field that extent produced.

THE CALIBRATION EXPERIMENT, AND WHY IT IS REPORTED AS A NEGATIVE RESULT.
The obvious next move is to stop defending 0.3 and instead *choose* a threshold
that guarantees a false-negative rate. :func:`nested_lofo_calibration` runs that
move honestly: for each held-out fire, pick the largest lambda whose FNR on the
other five fires is within budget, then measure what that lambda does on the
fire it never saw. Two budgets are reported.

* **naive** — target FNR 0.20 on the calibration fires, no finite-sample term.
* **conformal** — target 0.20 minus the leave-one-out finite-sample correction
  ``1 / (n + 1)`` with ``n = 5`` calibration fires, i.e. 0.0333
  (Angelopoulos, Bates, Fisch, Lei & Schuster, *Conformal Risk Control*, ICLR
  2024, https://proceedings.iclr.cc/paper_files/paper/2024/file/f3549ef9b5ff520a7e41ff3cc306ab2b-Paper-Conference.pdf).

At ``n = 6`` fires the correction is not a nuisance term: ``1/6 = 0.167`` eats
83 % of a 0.20 budget. That single arithmetic fact is the finding, and both
columns are reported because neither alone is the result — see
``docs/operating_point.md``.

⚠ **EXCHANGEABILITY DOES NOT HOLD HERE, so neither column is a guarantee.**
Two separate breaks, either one sufficient: (1) the out-of-fold probability for
a cell in fire *g* comes from a model trained on the other five fires, so the
"calibration" fires and the held-out fire are not exchangeable draws — the
calibration set is entangled with the model that scored the test set; (2) the
correction ``1/(n+1)`` is a **fire-level** finite-sample term while the quantile
is taken over **cells**, and the cells within one fire are neither independent
nor identically distributed with cells in another. The corrected column is
therefore an optimistic bound on what a real guarantee would cost, not the
guarantee itself. It is reported to show that even the optimistic version is
unusable.

⚠ **NO DEFAULT IS CHANGED BY THIS SCRIPT.** No lambda computed here is adopted
anywhere. ``forward_sim_advance_threshold`` stays 0.3 and ``walk_cutoff_p``
stays 0.5; this is evidence about them, not a re-tuning of them.

Method proposed by the autonomous loop (WFG-019, brief section (d)); the
negative-result framing and the exchangeability caveat are the loop's, written
so the student can state them in ninety seconds.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]

PROC = REPO / "data" / "processed"
OOF_CELLS = PROC / "spread_v2_lofo_oof_cells.csv.gz"
METRICS = PROC / "oof_classification_metrics.json"
OUT_DIR = PROC / "operating_point"
OUT = OUT_DIR / "per_fire_recall.json"

#: docs/figures/ is a committed set that must not be regenerated (HANDOFF
#: §5.3). Everything this script draws goes to a NEW subdirectory.
FIG = REPO / "docs" / "figures" / "auto" / "pr_curve_operating_point.png"

#: config/default.yaml :: time.forward_sim_advance_threshold. A DEFAULT.
OPERATING_THRESHOLD = 0.3

#: config/default.yaml :: pedestrian.walk_cutoff_p. A DIFFERENT knob, named
#: here only so the artifact records that the two were not confused.
ROUTER_P_CUT = 0.5

#: The FNR budget the calibration experiment is asked to hold.
FNR_BUDGET = 0.20

#: Reported to three significant figures (docs/MODEL_CARD.md §precision rule).
SIG = 3


def sig3(x: float | None) -> float | None:
    """Round to three significant figures, or pass ``None`` through."""
    if x is None:
        return None
    if x == 0:
        return 0.0
    return float(f"%.{SIG}g" % x)


def load_cells() -> pd.DataFrame:
    if not OOF_CELLS.exists():  # pragma: no cover - guarded by the caller
        raise SystemExit(f"missing input: {OOF_CELLS}")
    return pd.read_csv(OOF_CELLS)


def per_fire_table(df: pd.DataFrame, threshold: float) -> dict:
    """Recall, FNR, positives and the maximum probability, one row per fire.

    ``max_prob_any_cell`` is over EVERY cell in the fold and
    ``max_prob_positive_cell`` only over the cells that actually ignited. The
    pair matters: a fire whose maximum over all cells sits below the threshold
    can never produce a true positive at it *or* a false one, which is a
    stronger statement than zero recall.
    """
    rows: dict[str, dict] = {}
    for fire in sorted(df["fire_id"].unique()):
        sub = df[df["fire_id"] == fire]
        pos = sub[sub["label"] == 1]
        n_pos = int(len(pos))
        hit = int((pos["prob"] >= threshold).sum())
        recall = hit / n_pos if n_pos else None
        rows[str(fire)] = {
            "n_cells": int(len(sub)),
            "n_positive": n_pos,
            "true_positives_at_threshold": hit,
            "recall": sig3(recall),
            "false_negative_rate": sig3(None if recall is None else 1.0 - recall),
            "max_prob_any_cell": sig3(float(sub["prob"].max())),
            "max_prob_positive_cell": sig3(float(pos["prob"].max())) if n_pos else None,
            "threshold_is_reachable": bool(float(sub["prob"].max()) >= threshold),
        }
    return rows


def lambda_for_budget(cal_pos: np.ndarray, target_fnr: float) -> float:
    """Largest threshold whose FNR on ``cal_pos`` is at most ``target_fnr``.

    FNR at a threshold t is ``mean(cal_pos < t)``. The function is a step
    function that only changes at the observed positive probabilities, so the
    candidates are those values and 0.0. Ties are handled by evaluating the
    achieved FNR at every candidate rather than by indexing a sorted array,
    which would silently overshoot when several positives share a probability.

    Convention, stated because the two Round-3 verdicts used different ones and
    disagreed on lambda as a result: the comparison is STRICT (``<``), so a
    positive exactly at lambda counts as caught, and lambda is the LARGEST
    feasible candidate rather than the smallest — the least conservative choice
    that still meets the budget.
    """
    if target_fnr <= 0:
        return 0.0
    cand = np.concatenate([[0.0], np.unique(cal_pos)])
    achieved = (cal_pos[None, :] < cand[:, None]).mean(axis=1)
    feasible = cand[achieved <= target_fnr + 1e-12]
    return float(feasible.max()) if len(feasible) else 0.0


def nested_lofo_calibration(df: pd.DataFrame, budget: float) -> dict:
    """Hold out each fire; calibrate lambda on the other five; measure the cost.

    Returns one block per convention (``naive`` and ``conformal``), each with a
    row per held-out fire. ``flagged_fraction_all_cells`` is the share of the
    WHOLE 151,904-row dataset that lambda flags, which is the number to read
    against the 1.97 % prevalence; ``flagged_fraction_held_out`` is the same
    share within the fire that was held out.
    """
    fires = sorted(df["fire_id"].unique())
    n_cal = len(fires) - 1
    correction = 1.0 / (n_cal + 1)
    out: dict = {
        "budget_fnr": budget,
        "n_fires": len(fires),
        "n_calibration_fires": n_cal,
        "finite_sample_correction": sig3(correction),
        "correction_share_of_budget": sig3(correction / budget),
        "conventions": {},
    }
    for name, target in (
        ("naive", budget),
        ("conformal", budget - correction),
    ):
        rows: dict[str, dict] = {}
        for held in fires:
            cal = df[df["fire_id"] != held]
            ho = df[df["fire_id"] == held]
            cal_pos = cal.loc[cal["label"] == 1, "prob"].to_numpy()
            ho_pos = ho.loc[ho["label"] == 1, "prob"].to_numpy()
            lam = lambda_for_budget(cal_pos, target)
            rows[str(held)] = {
                "lambda": sig3(lam),
                "calibration_fnr": sig3(float((cal_pos < lam).mean())),
                "held_out_fnr": sig3(float((ho_pos < lam).mean())),
                "held_out_bound_holds": bool(float((ho_pos < lam).mean()) <= budget),
                "flagged_fraction_held_out": sig3(float((ho["prob"] >= lam).mean())),
                "flagged_fraction_all_cells": sig3(float((df["prob"] >= lam).mean())),
            }
        held_out = [r["held_out_fnr"] for r in rows.values()]
        flagged = [r["flagged_fraction_all_cells"] for r in rows.values()]
        out["conventions"][name] = {
            "target_fnr_on_calibration_fires": sig3(target),
            "per_held_out_fire": rows,
            "n_held_out_bound_holds": sum(r["held_out_bound_holds"] for r in rows.values()),
            "held_out_fnr_max": sig3(max(held_out)),
            "flagged_fraction_all_cells_min": sig3(min(flagged)),
            "flagged_fraction_all_cells_max": sig3(max(flagged)),
        }
    return out


def build(df: pd.DataFrame) -> dict:
    metrics = json.loads(METRICS.read_text())
    per_fire = per_fire_table(df, OPERATING_THRESHOLD)
    calib = nested_lofo_calibration(df, FNR_BUDGET)

    pooled_pos = df[df["label"] == 1]
    pooled_recall = float((pooled_pos["prob"] >= OPERATING_THRESHOLD).mean())
    fold_recalls = [
        r["recall"] for r in per_fire.values() if r["recall"] is not None
    ]
    mean_of_folds = float(np.mean(fold_recalls))

    prevalence = float(df["label"].mean())
    return {
        "schema_version": 1,
        "title": "Operating-point evidence — per-fire recall at 0.3 and the "
                 "nested leave-one-fire-out threshold calibration",
        "source_file": str(OOF_CELLS.relative_to(REPO)),
        "n_rows": int(len(df)),
        "n_positive": int(len(pooled_pos)),
        "prevalence": sig3(prevalence),
        "operating_threshold": OPERATING_THRESHOLD,
        "operating_threshold_origin":
            "config/default.yaml :: time.forward_sim_advance_threshold. Applied "
            "PER SIMULATION STEP to a per-step ignition probability. NOT the "
            "router's cut: the router thresholds the CUMULATIVE "
            "survival-accumulated field at pedestrian.walk_cutoff_p = 0.5. "
            "Neither was tuned on these probabilities.",
        "router_p_cut": ROUTER_P_CUT,
        "no_model_was_fitted":
            "Probabilities are read from the committed LOGO-CV out-of-fold file; "
            "nothing was retrained and no default was changed.",
        "per_fire": per_fire,
        "pooled_recall": sig3(pooled_recall),
        "mean_of_folds_recall": sig3(mean_of_folds),
        "cross_check": {
            "note": "Recomputed here from the cell-level file; must agree with "
                    "the Session 18 values in oof_classification_metrics.json.",
            "pooled_recall_in_metrics_file": metrics["pooled"]["recall"],
            "mean_of_folds_recall_in_metrics_file":
                metrics["mean_of_folds"]["recall"],
            "pooled_agrees": bool(
                abs(sig3(pooled_recall) - metrics["pooled"]["recall"]) < 1e-9
            ),
            "mean_of_folds_agrees": bool(
                abs(sig3(mean_of_folds) - metrics["mean_of_folds"]["recall"]) < 1e-9
            ),
        },
        "threshold_calibration": calib,
        "leakage_caveat":
            "The out-of-fold probability for a cell in fire g comes from a model "
            "trained on the other five fires, so the calibration fires are not "
            "exchangeable with the held-out fire and the conformal correction "
            "does not deliver a valid finite-sample guarantee here. It is a "
            "fire-level term applied to a cell-level quantile besides. Both "
            "columns are reported as evidence about the threshold, not as a "
            "bound on it.",
        "what_this_does_not_show":
            "It does not show the routing field's miss rate (different surface, "
            "different cut); it does not rank the six fires on model quality "
            "(three of them contribute 8, 24 and 34 positives); and it does not "
            "license any lambda computed here as an operating point.",
    }


def draw_figure(df: pd.DataFrame, path: Path) -> None:
    """PR curve with the untuned 0.3 point and the F1-optimal 0.14 point marked."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = json.loads(METRICS.read_text())
    pts = [p for p in metrics["pr_curve"]["points"] if p["precision"] is not None]
    rec = [p["recall"] for p in pts]
    pre = [p["precision"] for p in pts]
    prev = metrics["pr_curve"]["prevalence"]
    f1pt = metrics["f1_maximising_threshold_NOT_ADOPTED"]

    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=160)
    ax.plot(rec, pre, "-", color="#1f4e79", lw=1.8, label="OOF precision-recall")
    ax.axhline(prev, color="#999999", ls="--", lw=1.2,
               label=f"no-skill baseline = prevalence {prev:.4f}")

    ax.plot([metrics["pooled"]["recall"]], [metrics["pooled"]["precision"]],
            "o", ms=9, color="#c00000", zorder=5,
            label=f"operating point 0.3 (untuned): recall "
                  f"{metrics['pooled']['recall']:.3f}")
    ax.plot([f1pt["recall"]], [f1pt["precision"]], "s", ms=8, color="#e07b00",
            zorder=5,
            label=f"F1-optimal {f1pt['threshold']} (NOT adopted): recall "
                  f"{f1pt['recall']:.3f}")

    ax.set_xlabel("recall (fraction of igniting cells flagged)")
    ax.set_ylabel("precision")
    ax.set_title("Out-of-fold precision-recall, six leave-one-fire-out folds\n"
                 f"average precision {metrics['pr_curve']['average_precision']:.3f}"
                 f" against a {prev:.4f} no-skill baseline", fontsize=10)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(0, max(pre) * 1.15)
    ax.grid(alpha=0.25, lw=0.6)
    ax.legend(fontsize=7.5, loc="upper right", framealpha=0.95)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--figure", action="store_true",
                    help="also draw the PR-curve panel")
    args = ap.parse_args()

    df = load_cells()
    payload = build(df)

    cc = payload["cross_check"]
    if not (cc["pooled_agrees"] and cc["mean_of_folds_agrees"]):
        print("REFUSING TO WRITE: recomputed recall disagrees with the "
              "committed Session 18 metrics.", file=sys.stderr)
        print(json.dumps(cc, indent=2), file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}")

    for fire, r in payload["per_fire"].items():
        print(f"  {fire:<22} n+={r['n_positive']:>5}  recall={r['recall']}"
              f"  FNR={r['false_negative_rate']}"
              f"  max_p={r['max_prob_any_cell']}")
    cal = payload["threshold_calibration"]
    for name, blk in cal["conventions"].items():
        print(f"  calibration[{name}] target={blk['target_fnr_on_calibration_fires']}"
              f"  bound holds held-out on {blk['n_held_out_bound_holds']}/6"
              f"  flags {blk['flagged_fraction_all_cells_min']}"
              f"-{blk['flagged_fraction_all_cells_max']} of all cells")

    if args.figure:
        draw_figure(df, FIG)
        print(f"wrote {FIG.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
