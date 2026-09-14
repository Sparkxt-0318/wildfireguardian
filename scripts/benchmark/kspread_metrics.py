#!/usr/bin/env python
"""The four K-SPREAD-2025 metrics (protocol ``docs/benchmark/K_SPREAD_2025.md`` §5).

The protocol fixes what is measured. It does not fix every convention a scorer needs, so
the ones below are DECLARED here, before any entrant was run, and are repeated in
``docs/benchmark/results_v0.1.md``. None of them was chosen after seeing a score.

C1 — TIME. An entrant's stack gives probability at its own surface times. Probability at
     an arbitrary time is linear between the two bracketing surfaces and clamped outside
     them: ``wildfireguardian.routing.hazard.HazardSequence``'s own rule, so the benchmark
     reads a field the way this repository's router already reads it. An entrant's arrival
     time at a cell is the linearly-interpolated first crossing of p >= 0.5; a field that
     never reaches 0.5 by its last surface 「calls the cell safe」 and its arrival is ``inf``.
     The clamp means a crossing after the last surface is never detected, which understates
     late arrivals; the affected count is reported rather than corrected.

C2 — SPACE. Metrics 1-3 sample by A5 cell membership (``kspread_truth.cell_index``), the
     same floor arithmetic ``scripts/regrade_three_way.py::classify_route`` uses, for the
     entrant and for the truth alike. Not the router's bilinear sampler: on a binary
     footprint that is the softer reading (``docs/regrade_three_way.md`` §A5's correction,
     §6). Metric 3 also reports the bilinear variant so the gap is a number, not a worry.

C3 — TRUTH. ``kspread_truth`` under ``docs/regrade_three_way.md`` §2 A1-A6, miss allowance
     *m* = 0 as the headline, *m* = 1 and ∞ reported. Indeterminate cells enter neither the
     AUC nor the IoU, in either the numerator or the denominator, and are counted as
     unscorable (protocol §5.2).

C4 — RESOLUTION. Protocol §4 targets a 100 m grid and says a 500 m entrant is upsampled by
     nearest neighbour and says so. Both v0.1 entrants are 500 m and the only committed
     truth is the 500 m ``obs_stack``, so nearest-neighbour upsampling of BOTH to 100 m
     replaces each cell by 25 identical cells and changes no metric in §5.1-§5.3.
     ``tests/test_kspread_scorer.py`` asserts that identity rather than assuming it. v0.1
     therefore scores on the native 500 m grid and says so here.

C5 — METRIC 3'S NODE SET. 「every walk-network node the canonical routing scans」 is the
     canonical 영덕 scan's own origin set — ``candidate_origins`` on the CANONICAL field,
     the 458 nodes ``data/processed/real_roads_real_hazard_canonical.json`` was measured
     on. It is held fixed across entrants, exactly as ``run_leakfree_yeongdeok_fold.py``
     holds it fixed ("SAME origin set, by rule"); an entrant does not get to choose which
     nodes it is judged on. Nodes outside the grid are unsupported and never scored.

C6 — METRIC 4'S CLASSES. ``docs/last_safe_departure.md`` reports LSD as a minute on a
     10-minute grid with -1 for 「never」 and 600 for 「censored」, and reads it through three
     cuts: never, before 5 h, and censored. The class here is that page's own partition,
     written out: ``never`` (-1), ``closes_before_5h`` (0 <= LSD < 300),
     ``closes_after_5h`` (300 <= LSD < 600), ``censored`` (LSD >= 600).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kspread_truth import (  # noqa: E402
    CLASSES, DETECTED, INDETERMINATE, NOT_DETECTED, horizon_truth,
)

#: Metric 4's class edges in minutes (C6).
LSD_NEVER, LSD_FIVE_HOURS, LSD_CENSORED = -1.0, 300.0, 600.0


# --- C1: reading an entrant's field -----------------------------------------------

def surface_at(stack: np.ndarray, times: np.ndarray, t_min: float) -> np.ndarray:
    """Probability grid at ``t_min``: linear between bracketing surfaces, clamped outside."""
    times = np.asarray(times, float)
    if t_min <= times[0]:
        return np.asarray(stack[0], float).copy()
    if t_min >= times[-1]:
        return np.asarray(stack[-1], float).copy()
    j = int(np.searchsorted(times, t_min, side="right"))
    i0, i1 = j - 1, j
    frac = (t_min - times[i0]) / (times[i1] - times[i0])
    return np.asarray(stack[i0], float) * (1 - frac) + np.asarray(stack[i1], float) * frac


def crossing_grid(stack: np.ndarray, times: np.ndarray, p_cut: float = 0.5) -> np.ndarray:
    """Per-cell first time p >= ``p_cut``, linearly interpolated in time; ``inf`` if never (C1)."""
    stack = np.asarray(stack, float)
    times = np.asarray(times, float)
    out = np.full(stack.shape[1:], np.inf)
    hit = stack[0] >= p_cut
    out[hit] = float(times[0])
    for k in range(1, len(times)):
        prev, cur = stack[k - 1], stack[k]
        new = (~np.isfinite(out)) & (cur >= p_cut)
        if not new.any():
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            denom = np.where(cur > prev, cur - prev, np.nan)
            frac = np.clip((p_cut - prev) / denom, 0.0, 1.0)
        frac = np.where(np.isfinite(frac), frac, 0.0)
        out[new] = times[k - 1] + frac[new] * (times[k] - times[k - 1])
    return out


# --- metric 1 and 2 ---------------------------------------------------------------

def auc_iou_at_horizon(stack, times, fs, t, horizon_min: float, m=0, p_cut: float = 0.5) -> dict:
    """Protocol §5.1 and §5.2 at one horizon, with indeterminate cells excluded (C3)."""
    from wildfireguardian.spread_v2.model import _safe_auc, cell_iou

    p = surface_at(stack, times, horizon_min)
    truth = horizon_truth(fs, t, horizon_min, m)
    scorable = truth[DETECTED] | truth[NOT_DETECTED]
    y = truth[DETECTED][scorable].astype(int)
    auc = _safe_auc(y, p[scorable]) if y.size else None
    pred = p >= p_cut
    iou = float(cell_iou(pred & scorable, truth[DETECTED] & scorable)) if scorable.any() else None
    union = int((((pred & scorable) | (truth[DETECTED] & scorable))).sum())
    return {
        "horizon_min": float(horizon_min),
        "miss_allowance": m,
        "roc_auc": auc,
        "iou_at_p_ge_0.5": iou if union else None,
        "cells_total": int(truth[DETECTED].size),
        "cells_by_truth_class": {c: int(truth[c].sum()) for c in CLASSES},
        "cells_unscorable_indeterminate": int(truth[INDETERMINATE].sum()),
        "cells_predicted_positive": int(pred.sum()),
        "cells_predicted_positive_indeterminate": int((pred & truth[INDETERMINATE]).sum()),
        "iou_intersection": int((pred & truth[DETECTED] & scorable).sum()),
        "iou_union": union,
    }


# --- metric 3 ---------------------------------------------------------------------

def arrival_time_error(nodes: list[dict], window_min: float, p_cut: float = 0.5) -> dict:
    """Protocol §5.3 from per-node ``{model_min, observed_min, earliest_min, supported}`` rows.

    ``model_min`` and ``observed_min`` are minutes from T0, ``inf`` where the entrant never
    crosses ``p_cut`` / the observation never detects the cell. The signed error is
    ``model - observed``: positive means the entrant calls the fire LATE, which is the
    direction that strands people.

    ⚠ **``window_min`` is not a detail.** An entrant's field ends at its last surface, and
    the 영덕 observation runs to 2403 min --- four overpasses past it. Scored against the
    whole observation record, an entrant is charged for every road node the fire reached
    after its horizon, which measures the horizon and not the entrant. So the headline
    counts run over a COMMON window: the observation 「calls a node burned」 only if it
    detected the node's cell by ``window_min``. ``whole_observation_record`` below repeats
    every count against the full record so the restriction hides nothing.
    """
    sup = [n for n in nodes if n["supported"]]
    out = {"nodes_scanned": len(nodes), "nodes_unsupported": len(nodes) - len(sup),
           "nodes_supported": len(sup), "window_min": float(window_min)}
    out.update(_counts(sup, window_min, window_min))
    out["whole_observation_record"] = _counts(sup, window_min, math.inf)
    return out


def _counts(sup: list[dict], window: float, obs_window: float) -> dict:
    """``window`` bounds the ENTRANT's horizon; ``obs_window`` what counts as observed-burned."""
    burned = (lambda n, w: math.isfinite(n["observed_min"]) and n["observed_min"] <= w)
    fires = (lambda n, w: math.isfinite(n["model_min"]) and n["model_min"] <= w)
    obs_burn = [n for n in sup if burned(n, obs_window)]
    model_burn = [n for n in sup if fires(n, window)]
    both = [n for n in obs_burn if fires(n, window)]
    err = np.array([n["model_min"] - n["observed_min"] for n in both], float)
    err_e = np.array([n["model_min"] - n["earliest_min"] for n in both], float)
    model_safe = [n for n in sup if not fires(n, window)]
    false_safe = [n for n in model_safe if burned(n, obs_window)]
    false_alarm = [n for n in model_burn if not burned(n, obs_window)]
    q = (lambda a, f: float(np.percentile(a, f)) if a.size else None)
    return {
        "nodes_observation_burns": len(obs_burn),
        "nodes_model_burns": len(model_burn),
        "nodes_both_burn": len(both),
        "median_abs_error_min": float(np.median(np.abs(err))) if err.size else None,
        "mean_abs_error_min": float(np.mean(np.abs(err))) if err.size else None,
        "median_signed_error_min": float(np.median(err)) if err.size else None,
        "signed_error_p25_min": q(err, 25),
        "signed_error_p75_min": q(err, 75),
        "median_abs_error_vs_earliest_min": float(np.median(np.abs(err_e))) if err_e.size else None,
        "nodes_model_calls_safe": len(model_safe),
        "false_safe_nodes": len(false_safe),
        "false_safe_rate": (len(false_safe) / len(model_safe)) if model_safe else None,
        "false_alarm_nodes": len(false_alarm),
        "nodes_model_late": int((err > 0).sum()),
        "nodes_model_early": int((err < 0).sum()),
        "nodes_model_exact": int((err == 0).sum()),
        "observation_window_min": (None if not math.isfinite(obs_window) else float(obs_window)),
        "nodes_observation_indeterminate_at_window": sum(
            1 for n in sup if n["earliest_min"] <= window < n["observed_min"]),
    }


# --- metric 4 ---------------------------------------------------------------------

def lsd_class(lsd: float) -> str:
    """C6: ``docs/last_safe_departure.md``'s own cuts, written out as a partition."""
    if lsd <= LSD_NEVER:
        return "never"
    if lsd < LSD_FIVE_HOURS:
        return "closes_before_5h"
    if lsd < LSD_CENSORED:
        return "closes_after_5h"
    return "censored"


def decision_shift(entrant_lsd: dict[int, float], truth_lsd: dict[int, float],
                   weights: dict[int, int]) -> dict:
    """Protocol §5.4: buildings whose LSD class differs between entrant and truth field."""
    shifted = 0
    total = 0
    table: dict[str, int] = {}
    for n, w in weights.items():
        if n not in entrant_lsd or n not in truth_lsd:
            continue
        a, b = lsd_class(entrant_lsd[n]), lsd_class(truth_lsd[n])
        total += w
        table[f"{a}|{b}"] = table.get(f"{a}|{b}", 0) + w
        if a != b:
            shifted += w
    optimistic = sum(w for k, w in table.items()
                     if _rank(k.split("|")[0]) > _rank(k.split("|")[1]))
    return {
        "buildings_scored": total,
        "buildings_class_changed": shifted,
        "buildings_entrant_more_optimistic": optimistic,
        "class_table_entrant_given_truth": dict(sorted(table.items())),
    }


def _rank(cls: str) -> int:
    return {"never": 0, "closes_before_5h": 1, "closes_after_5h": 2, "censored": 3}[cls]


__all__ = [
    "arrival_time_error", "auc_iou_at_horizon", "crossing_grid", "decision_shift",
    "lsd_class", "surface_at",
]
