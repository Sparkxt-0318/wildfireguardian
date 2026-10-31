"""Cross-fitted Phase 0 runs: whole-fire folds -> coherent members at matched K -> one additive score row per window.

Dev: for each SPLITS fold, the baseline and the calibrated-dilation reference are fitted on the dev fires of the
other folds and predict the fires of the held-out fold (leave a group of whole fires out). Test (milestones only):
fitted on all dev fires. c651 is frozen (nothing fitted) and in-sample on its training fires: ``in_sample``.

Scored cells of a window: domain & not burned at the cutoff & comparison inputs valid (wind and slope are loaded
for every baseline) & supported by the model and the reference. Persistence and calibrated best dilation are
scored on the same cells in the same row, so Brier skill against both uses identical cells; ``mask_sha256`` checks
that rows of separate runs scored identical cells (``leaderboard`` refuses rows that differ).

Rows hold additive terms of every METRICS.md metric (``TERM_COLUMNS``; lists are JSON): pool windows and fires by
summing, and resample whole fires with ``metrics.fire_bootstrap`` for intervals (``firecast_lab.leaderboard``).
The forecast ``p`` is the member share (what Track C receives), the arrival-time metrics use the members' hourly
lattice, and rank-histogram ties are broken with the window seed.
"""
from __future__ import annotations

import hashlib
import json
from typing import Callable, Iterable, Iterator

import numpy as np

from firecast_lab import baselines as bl
from firecast_lab import metrics as m
from firecast_lab.data import Window, case_seed
from firecast_lab.members import burned_by

FSS_COLUMNS = tuple(f"fss_{part}_{n}" for n in m.FSS_SIZES for part in ("num", "den"))
LIST_COLUMNS = ("rel_count", "rel_forecast_sum", "rel_observed_sum", "pr_cells", "pr_positives", "rank_counts",
                "spread_row_cells", "spread_row_var_sum", "spread_row_err2_sum")
TERM_COLUMNS = ("rel_count", "rel_forecast_sum", "rel_observed_sum",       # reliability rows (p == 0, then bins)
                "pr_cells", "pr_positives",                                # per member count 0..K: average precision
                *FSS_COLUMNS,                                              # FSS terms per neighbourhood size
                "rank_counts", "rank_fully_tied",                          # rank histogram of the arrival hour
                "spread_var_sum", "spread_err2_sum",                       # spread-skill, all cells
                "spread_row_cells", "spread_row_var_sum", "spread_row_err2_sum")   # ... per fixed spread row
SCORE_COLUMNS = ("n_cells", "positives", "removed_by_support", "brier_sum", "brier_prob_sum",
                 "brier_persistence_sum", "brier_reference_sum", "crps_sum", "crps_fair_sum", "zero_prob_positives",
                 "mask_sha256", *TERM_COLUMNS)
COLUMNS = ("baseline", "split", "fold", "fire", "country", "cutoff_utc", "lead_h", "members", "coupling",
           "length_cells", "in_sample", "synthetic", "window_seed", *SCORE_COLUMNS, "fit")
TERM_DEFINITIONS = dict(reliability_edges=list(m.RELIABILITY_EDGES), fss_sizes=list(m.FSS_SIZES),
                        spread_sd_edges_h=list(m.SPREAD_SD_EDGES_H), p="member share",
                        arrival="hourly lattice 1..L+1", rank_ties="window seed")


def crossfit(name: str, split: str, windows_of: Callable[[list[str]], Iterable[Window]], splits: dict, *,
             options: dict | None = None) -> Iterator[tuple[Window, object, object]]:
    """``(window, model, reference)`` for every window of the split, each fitted without the window's fire group.
    ``windows_of(fire_ids)`` returns a re-iterable of windows (a ``data.WindowSource`` or a list)."""
    dev = [f for f in splits["fires"] if f["split"] == "dev"]
    if split == "dev":
        folds = sorted({f["fold"] for f in dev})
        groups = [([f["id"] for f in dev if f["fold"] != k], [f["id"] for f in dev if f["fold"] == k]) for k in folds]
    elif split == "test":
        groups = [([f["id"] for f in dev], [f["id"] for f in splits["fires"] if f["split"] == "test"])]
    else:
        raise ValueError("split must be 'dev' or 'test'; the fresh holdout stays locked")
    for train_ids, predict_ids in groups:
        train = windows_of(train_ids)
        reference = bl.CalibratedDilation().fit(train)
        model = reference if name == "calibrated_dilation" else bl.make(name, **(options or {})).fit(train)
        for window in windows_of(predict_ids):
            yield window, model, reference


def mask_digest(mask: np.ndarray) -> str:
    return hashlib.sha256(np.packbits(mask).tobytes() + repr(mask.shape).encode()).hexdigest()[:16]


def window_terms(y, members_burning, lattice, observed, mask, *, K: int, seed: int) -> dict:
    """The additive per-window terms of ``TERM_COLUMNS`` on the scored cells ``mask`` (zeros on an empty mask).

    ``y``: new burn by the lead; ``members_burning``: how many of the K members newly burn each cell by the lead (the
    forecast is the share, ``members_burning / K``); ``lattice`` ``[K, ...]`` and ``observed``: hourly arrival
    lattices; ``seed``: breaks rank ties. List terms are JSON. Spread terms are NaN (lists empty) when K < 2."""
    n_rel, n_spread = len(m.RELIABILITY_EDGES), len(m.SPREAD_SD_EDGES_H) + 2
    terms = dict(rel_count=[0] * n_rel, rel_forecast_sum=[0.0] * n_rel, rel_observed_sum=[0.0] * n_rel,
                 pr_cells=[0] * (K + 1), pr_positives=[0] * (K + 1), **dict.fromkeys(FSS_COLUMNS, 0.0),
                 rank_counts=[0] * (K + 1), rank_fully_tied=0, spread_var_sum=0.0, spread_err2_sum=0.0,
                 spread_row_cells=[0] * n_spread, spread_row_var_sum=[0.0] * n_spread,
                 spread_row_err2_sum=[0.0] * n_spread)
    if K < 2:
        terms.update(spread_var_sum=float("nan"), spread_err2_sum=float("nan"), spread_row_cells=[],
                     spread_row_var_sum=[], spread_row_err2_sum=[])
    if mask.any():
        p = members_burning / K
        rel = m.reliability(y, p, mask)
        cells, positives = m.level_counts(y, members_burning, mask, K + 1)
        rank = m.rank_histogram(lattice, observed, mask, seed=seed)
        terms.update(rel_count=[r["count"] for r in rel], rel_forecast_sum=[r["forecast_sum"] for r in rel],
                     rel_observed_sum=[r["observed_sum"] for r in rel], pr_cells=cells.tolist(),
                     pr_positives=positives.tolist(), rank_counts=rank["counts"], rank_fully_tied=rank["fully_tied"])
        for n in m.FSS_SIZES:
            num, den = m.fss_terms(y, p, mask, n)
            terms[f"fss_num_{n}"], terms[f"fss_den_{n}"] = float(num.sum()), float(den.sum())
        if K > 1:
            var, err2 = m.spread_skill_terms(lattice, observed, mask)
            row = m.spread_rows(var)
            terms.update(spread_var_sum=float(var.sum()), spread_err2_sum=float(err2.sum()),
                         spread_row_cells=np.bincount(row, minlength=n_spread).tolist(),
                         spread_row_var_sum=np.bincount(row, weights=var, minlength=n_spread).tolist(),
                         spread_row_err2_sum=np.bincount(row, weights=err2, minlength=n_spread).tolist())
    return {k: json.dumps(v) if k in LIST_COLUMNS else v for k, v in terms.items()}


def score_window(window: Window, hours: np.ndarray, reference_hours: np.ndarray, *, seed: int,
                 probability: np.ndarray | None = None) -> dict:
    """Additive scores of one window at its lead on the cells every compared forecast supports (module doc).

    ``brier_sum`` uses the member share (what Track C receives); ``brier_prob_sum`` the model's probability field
    when it has one (the member Brier adds about mean p(1 - p) / K). Persistence forecasts p = 0. ``seed``: the
    window seed (rank-histogram ties). The other terms: ``window_terms``."""
    lead = window.lead_h
    base = window.fitting_rows
    supported = ~np.isnan(hours).any(axis=0) & ~np.isnan(reference_hours).any(axis=0)
    mask = base & supported
    y = ((window.outcome_h > 0) & (window.outcome_h <= lead)).astype(np.float64)
    n, K = int(mask.sum()), hours.shape[0]
    with np.errstate(invalid="ignore"):
        burning = ((hours > 0) & (hours <= lead)).sum(axis=0)
    lattice, observed = m.hourly_arrival(hours, lead), m.hourly_arrival(window.outcome_h, lead)
    row = dict(n_cells=n, positives=int(y[mask].sum()), removed_by_support=int((base & ~supported).sum()),
               mask_sha256=mask_digest(mask), brier_sum=0.0, brier_prob_sum=float("nan"),
               brier_persistence_sum=float(y[mask].sum()), brier_reference_sum=0.0, crps_sum=0.0,
               crps_fair_sum=float("nan"), zero_prob_positives=0,
               **window_terms(y, burning, lattice, observed, mask, K=K, seed=seed))
    if n == 0:
        return row
    p = burned_by(hours, lead)
    row.update(brier_sum=n * m.brier(y, p, mask), brier_reference_sum=n * m.brier(y, burned_by(reference_hours, lead),
                                                                                  mask),
               crps_sum=float(m.crps_arrival_terms(lattice, observed, mask, lead).sum()),
               zero_prob_positives=int((mask & (p == 0) & (y == 1)).sum()))
    if probability is not None:
        row["brier_prob_sum"] = n * m.brier(y, probability, mask)
    if K > 1:
        row["crps_fair_sum"] = float(m.crps_arrival_terms(lattice, observed, mask, lead, fair=True).sum())
    return row


def run(name: str, split: str, windows_of, splits: dict, *, K: int, seed: int, coupling: str = "shared",
        length_cells: float | None = None, options: dict | None = None) -> list[dict]:
    """Score rows (``COLUMNS``) of every window of the split for one baseline, cross-fitted as in ``crossfit``."""
    rows = []
    for window, model, reference in crossfit(name, split, windows_of, splits, options=options):
        draw = dict(K=K, seed=seed, coupling=coupling, length_cells=length_cells)
        hours, probability = bl.forecast(model, window, **draw)
        reference_hours = hours if reference is model else bl.forecast(reference, window, **draw)[0]
        record = window.record
        window_seed = case_seed(seed, window.fire, window.cutoff_utc)
        rows.append(dict(baseline=name, split=split, fold=record.get("fold"), fire=window.fire,
                         country=record.get("country"), cutoff_utc=window.cutoff_utc, lead_h=window.lead_h,
                         members=K, coupling=coupling, length_cells=length_cells,
                         in_sample=name == "c651" and record.get("c651_role") == "train+validation",
                         synthetic=window.synthetic, window_seed=window_seed,
                         **score_window(window, hours, reference_hours, seed=window_seed, probability=probability),
                         fit=json.dumps(model.describe(), sort_keys=True, default=str)))
    return rows
