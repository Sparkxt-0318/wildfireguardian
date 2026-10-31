"""Cross-fitted Phase 0 runs: whole-fire folds -> coherent members at matched K -> one additive score row per window.

Dev: for each SPLITS fold, the baseline and the calibrated-dilation reference are fitted on the dev fires of the
other folds and predict the fires of the held-out fold (leave a group of whole fires out). Test (milestones only):
fitted on all dev fires. c651 is frozen (nothing fitted) and in-sample on its training fires: ``in_sample``.

Scored cells of a window: domain & not burned at the cutoff & comparison inputs valid (wind and slope are loaded
for every baseline) & supported by the model and the reference. Persistence and calibrated best dilation are
scored on the same cells in the same row, so Brier skill against both uses identical cells; ``mask_sha256`` checks
that rows of separate runs scored identical cells. Rows hold sums: pool by summing, and resample whole fires with
``metrics.fire_bootstrap`` for intervals.
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

SCORE_COLUMNS = ("n_cells", "positives", "removed_by_support", "brier_sum", "brier_prob_sum",
                 "brier_persistence_sum", "brier_reference_sum", "crps_sum", "crps_fair_sum", "zero_prob_positives",
                 "mask_sha256")
COLUMNS = ("baseline", "split", "fold", "fire", "country", "cutoff_utc", "lead_h", "members", "coupling",
           "length_cells", "in_sample", "synthetic", "window_seed", *SCORE_COLUMNS, "fit")


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


def score_window(window: Window, hours: np.ndarray, reference_hours: np.ndarray, *,
                 probability: np.ndarray | None = None) -> dict:
    """Additive scores of one window at its lead on the cells every compared forecast supports (module doc).

    ``brier_sum`` uses the member share (what Track C receives); ``brier_prob_sum`` the model's probability field
    when it has one (the member Brier adds about mean p(1 - p) / K). Persistence forecasts p = 0."""
    lead = window.lead_h
    base = window.fitting_rows
    supported = ~np.isnan(hours).any(axis=0) & ~np.isnan(reference_hours).any(axis=0)
    mask = base & supported
    y = ((window.outcome_h > 0) & (window.outcome_h <= lead)).astype(np.float64)
    n, K = int(mask.sum()), hours.shape[0]
    row = dict(n_cells=n, positives=int(y[mask].sum()), removed_by_support=int((base & ~supported).sum()),
               mask_sha256=mask_digest(mask), brier_sum=0.0, brier_prob_sum=float("nan"),
               brier_persistence_sum=float(y[mask].sum()), brier_reference_sum=0.0, crps_sum=0.0,
               crps_fair_sum=float("nan"), zero_prob_positives=0)
    if n == 0:
        return row
    p = burned_by(hours, lead)
    lattice, observed = m.hourly_arrival(hours, lead), m.hourly_arrival(window.outcome_h, lead)
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
        rows.append(dict(baseline=name, split=split, fold=record.get("fold"), fire=window.fire,
                         country=record.get("country"), cutoff_utc=window.cutoff_utc, lead_h=window.lead_h,
                         members=K, coupling=coupling, length_cells=length_cells,
                         in_sample=name == "c651" and record.get("c651_role") == "train+validation",
                         synthetic=window.synthetic, window_seed=case_seed(seed, window.fire, window.cutoff_utc),
                         **score_window(window, hours, reference_hours, probability=probability),
                         fit=json.dumps(model.describe(), sort_keys=True, default=str)))
    return rows
