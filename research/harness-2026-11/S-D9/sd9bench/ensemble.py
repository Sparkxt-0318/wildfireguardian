"""Trajectory-level (joint-forecast) verification for burned area (A1 §5.3, revision 27).

Inputs are the existing entry-file contract: ``area_samples_<name>`` is a K x M array of
simulated new-burn cell counts per interval (one row per interval, one column per trajectory),
and the observed new-burn count per interval is derived from ``y`` (Entries.area_observed).

Metrics
  rank histogram   rank of the observed count among the M simulated counts, ties broken
                   uniformly at random (seeded), pooled over intervals and coarsened to
                   ``bins`` equal-width bins of the normalised rank (rank / M in [0, 1]).
                   Flat = calibrated; U = under-dispersed (over-confident); hump =
                   over-dispersed; slope = biased.
  flatness         chi-square statistic against the uniform histogram and its p-value
                   (descriptive: intervals within a fire are not independent), plus the
                   reliability index RI = sum_b |f_b - 1/bins|.
  spread-skill     mean ensemble variance vs squared error of the ensemble mean.
  CRPS             exact empirical-ensemble CRPS (score.crps_ensemble), reported by horizon.
All are descriptive per predictor; none is a decision criterion.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from .entries import Entries
from .score import crps_ensemble

RANK_SEED = 20261030


def ranks(samples: np.ndarray, observed: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Normalised ranks in [0, 1] for K intervals. samples: K x M, observed: K."""
    samples = np.asarray(samples, dtype=np.float64)
    observed = np.asarray(observed, dtype=np.float64)
    if samples.ndim != 2 or samples.shape[0] != observed.shape[0] or samples.shape[1] < 1:
        raise ValueError("samples must be K x M with K equal to len(observed)")
    below = (samples < observed[:, None]).sum(1)
    ties = (samples == observed[:, None]).sum(1)
    r = below + np.floor(rng.random(len(observed)) * (ties + 1))
    return r / samples.shape[1]


def rank_histogram(norm_ranks: np.ndarray, bins: int = 10) -> dict:
    norm_ranks = np.asarray(norm_ranks, dtype=np.float64)
    n = len(norm_ranks)
    idx = np.minimum((norm_ranks * bins).astype(int), bins - 1)
    counts = np.bincount(idx, minlength=bins)
    expected = n / bins
    chi2 = float(((counts - expected) ** 2 / expected).sum()) if n else None
    freq = counts / n if n else np.zeros(bins)
    return dict(n=n, bins=bins, counts=counts.tolist(), frequency=freq.tolist(),
                chi2=chi2, chi2_p=float(stats.chi2.sf(chi2, bins - 1)) if n else None,
                reliability_index=float(np.abs(freq - 1 / bins).sum()) if n else None,
                outer_share=float((counts[0] + counts[-1]) / n) if n else None,
                expected_outer_share=2 / bins)


def spread_skill(samples: np.ndarray, observed: np.ndarray) -> dict:
    samples = np.asarray(samples, dtype=np.float64)
    m = samples.shape[1]
    spread = float(samples.var(1, ddof=1).mean()) if m > 1 else None
    err = float(((samples.mean(1) - observed) ** 2).mean())
    # For a calibrated ensemble, E[(mean - y)^2] = (1 + 1/M) * E[var].
    return dict(mean_ensemble_variance=spread, mse_of_ensemble_mean=err,
                ratio=(err / ((1 + 1 / m) * spread)) if spread else None)


def area_ensemble_scores(entries: Entries, horizon_edges=(0.0, 12.0, 24.0, 36.0, 48.0), bins: int = 10,
                         seed: int = RANK_SEED) -> dict:
    """Joint-forecast scores per predictor that has area samples; UNAVAILABLE otherwise."""
    out = {}
    for name in entries.predictions:
        per_fire = entries.area_samples.get(name)
        if per_fire is None:
            out[name] = dict(status="UNAVAILABLE_NO_AREA_SAMPLES")
            continue
        rng = np.random.default_rng(seed)
        all_r, all_s, all_o, all_h, all_c = [], [], [], [], []
        for fire in sorted(per_fire):
            s = per_fire[fire]
            o = entries.area_observed[fire]
            m = entries.fire == fire
            hours = np.zeros(len(o))
            for k in range(len(o)):
                hk = entries.hours[m & (entries.interval == k)]
                hours[k] = hk[0] if len(hk) else np.nan
            all_r.append(ranks(s, o, rng))
            all_s.append(s)
            all_o.append(o)
            all_h.append(hours)
            all_c.append(np.array([crps_ensemble(s[k], o[k]) for k in range(len(o))]))
        widths = {x.shape[1] for x in all_s}
        r, o, h, c = (np.concatenate(v) for v in (all_r, all_o, all_h, all_c))
        rec = dict(status="SCORED", unit="new-burn cells", intervals=int(len(o)), trajectories=sorted(widths),
                   rank_histogram=rank_histogram(r, bins), mean_crps=float(c.mean()),
                   tie_break_seed=seed)
        if len(widths) == 1:
            rec["spread_skill"] = spread_skill(np.concatenate(all_s), o)
        rec["by_horizon"] = []
        for lo, hi in zip(horizon_edges[:-1], horizon_edges[1:]):
            use = (h > lo) & (h <= hi) if lo > 0 else (h >= lo) & (h <= hi)
            rec["by_horizon"].append(dict(lower=lo, upper=hi, intervals=int(use.sum()),
                                          mean_crps=float(c[use].mean()) if use.any() else None,
                                          rank_histogram=rank_histogram(r[use], bins) if use.any() else None))
        out[name] = rec
    return out
