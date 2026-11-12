"""Trajectory-level (joint-forecast) verification for burned area (A1 §5.3, revision 27).

Inputs are the existing entry-file contract: ``area_samples_<name>`` is a K x M array of
simulated new-burn cell counts per interval (one row per interval, one column per trajectory),
and the observed new-burn count per interval is derived from ``y`` (Entries.area_observed).

Metrics
  rank histogram   rank of the observed count among the M simulated counts, ties broken
                   uniformly at random (seeded). The integer rank r in 0..M is mapped to bin
                   floor((r + 0.5) / (M + 1) * bins). Expected bin counts are computed exactly
                   from the M + 1 equally likely ranks of each interval, so the test is unbiased
                   for any M (Hannah's note: r / M binning put rank M in the last bin and biased
                   small-M ensembles).
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
    """Integer ranks in 0..M for K intervals (ties broken uniformly). samples: K x M, observed: K."""
    samples = np.asarray(samples, dtype=np.float64)
    observed = np.asarray(observed, dtype=np.float64)
    if samples.ndim != 2 or samples.shape[0] != observed.shape[0] or samples.shape[1] < 1:
        raise ValueError("samples must be K x M with K equal to len(observed)")
    below = (samples < observed[:, None]).sum(1)
    ties = (samples == observed[:, None]).sum(1)
    r = below + np.floor(rng.random(len(observed)) * (ties + 1))
    return r.astype(np.int64)


def _bin(r, m, bins):
    return np.minimum(np.floor((np.asarray(r) + 0.5) / (np.asarray(m) + 1) * bins).astype(int), bins - 1)


def rank_histogram(r: np.ndarray, m, bins: int = 10) -> dict:
    """Histogram of integer ranks r (0..m) with exact expected bin probabilities.

    m is the ensemble size, a scalar or one per interval."""
    r = np.asarray(r, dtype=np.int64)
    n = len(r)
    m = np.broadcast_to(np.asarray(m, dtype=np.int64), r.shape)
    counts = np.bincount(_bin(r, m, bins), minlength=bins)
    expected = np.zeros(bins)
    for mv in np.unique(m):
        k = int((m == mv).sum())
        expected += k * np.bincount(_bin(np.arange(mv + 1), mv, bins), minlength=bins) / (mv + 1)
    ok = expected > 0
    chi2 = float(((counts[ok] - expected[ok]) ** 2 / expected[ok]).sum()) if n else None
    dof = int(ok.sum()) - 1
    freq = counts / n if n else np.zeros(bins)
    exp_freq = expected / n if n else np.zeros(bins)
    return dict(n=n, bins=bins, counts=counts.tolist(), frequency=freq.tolist(),
                expected_frequency=exp_freq.tolist(),
                chi2=chi2, chi2_p=float(stats.chi2.sf(chi2, dof)) if n and dof > 0 else None,
                reliability_index=float(np.abs(freq - exp_freq).sum()) if n else None,
                outer_share=float((counts[0] + counts[-1]) / n) if n else None,
                expected_outer_share=float(exp_freq[0] + exp_freq[-1]) if n else None)


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
        all_r, all_m, all_s, all_o, all_h, all_c = [], [], [], [], [], []
        for fire in sorted(per_fire):
            s = per_fire[fire]
            o = entries.area_observed[fire]
            m = entries.fire == fire
            hours = np.zeros(len(o))
            for k in range(len(o)):
                hk = entries.hours[m & (entries.interval == k)]
                hours[k] = hk[0] if len(hk) else np.nan
            all_r.append(ranks(s, o, rng))
            all_m.append(np.full(len(o), s.shape[1]))
            all_s.append(s)
            all_o.append(o)
            all_h.append(hours)
            all_c.append(np.array([crps_ensemble(s[k], o[k]) for k in range(len(o))]))
        widths = {x.shape[1] for x in all_s}
        r, mm, o, h, c = (np.concatenate(v) for v in (all_r, all_m, all_o, all_h, all_c))
        rec = dict(status="SCORED", unit="new-burn cells", intervals=int(len(o)), trajectories=sorted(widths),
                   rank_histogram=rank_histogram(r, mm, bins), mean_crps=float(c.mean()),
                   tie_break_seed=seed,
                   intervals_without_entries_not_in_any_horizon=int(np.isnan(h).sum()))
        if len(widths) == 1:
            rec["spread_skill"] = spread_skill(np.concatenate(all_s), o)
        rec["by_horizon"] = []
        for lo, hi in zip(horizon_edges[:-1], horizon_edges[1:]):
            use = (h > lo) & (h <= hi) if lo > 0 else (h >= lo) & (h <= hi)
            rec["by_horizon"].append(dict(lower=lo, upper=hi, intervals=int(use.sum()),
                                          mean_crps=float(c[use].mean()) if use.any() else None,
                                          rank_histogram=rank_histogram(r[use], mm[use], bins) if use.any() else None))
        out[name] = rec
    return out
