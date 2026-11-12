"""Lead-time design: survey-censored arrival scores (pre-registration addendum A1 §2 and §5).

File contract: one ``<fire>.npz`` per fire. N entries are (cell, cutoff) pairs
over cells unmapped at their cutoff. J is the largest number of later surveys
within the lead window, across the fire's cutoffs.

  cutoff        int    (N)     fire-local cutoff index into lead_hours
  n_leads       int    (N)     number of later surveys used for this entry, at least 1
  arrival_bin   int    (N)     0..n_leads. Bin j < n_leads means first mapped in
                               (t_j-1, t_j], with t_-1 the cutoff; n_leads means
                               not mapped by the last lead
  lead_hours    float  (C, J)  hours from cutoff to each later survey (NaN padding)
  cdf_<name>    float  (N, J)  predicted P(mapped by t_j), nondecreasing in j and in
                               [0, 1] for j < n_leads; NaN padding beyond

Scores:
  rps       sum over j < n_leads of (F_j - 1[arrival_bin <= j])^2. This is the
            ranked probability score over the n_leads + 1 censored arrival
            categories (unnormalized), the discrete analogue of arrival-time CRPS.
  by_lead   Brier of F_j against 1[arrival_bin <= j], pooled within lead-hour
            bins. These are the multi-horizon cumulative-extent scores.
Paired whole-fire bootstrap of the mean RPS difference uses the forecast-v2 scheme.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .score import DEFAULT_HORIZON_EDGES_H, DRAWS, SEED


@dataclass
class ArrivalEntries:
    fire: np.ndarray
    n_leads: np.ndarray
    arrival_bin: np.ndarray
    lead_hours: np.ndarray          # (N, J), per entry
    cdf: dict[str, np.ndarray]      # (N, J)


def _fail(path, msg):
    raise ValueError(f"{path.name}: {msg}")


def load_arrival(paths) -> ArrivalEntries:
    paths = sorted(Path(p) for p in paths)
    if not paths:
        raise ValueError("no arrival files given")
    jmax = 0
    raw = []
    names = None
    for path in paths:
        with np.load(path, allow_pickle=False) as z:
            for key in ("cutoff", "n_leads", "arrival_bin", "lead_hours"):
                if key not in z.files:
                    _fail(path, f"missing '{key}'")
            d = {k: z[k] for k in z.files}
        n = len(d["n_leads"])
        current = sorted(k[4:] for k in d if k.startswith("cdf_"))
        if names is None:
            names = current
        if current != names or not names:
            _fail(path, f"cdf predictors {current} differ from {names} or are empty")
        lh = d["lead_hours"].astype(np.float64)
        cutoff = d["cutoff"].astype(np.int64)
        nl = d["n_leads"].astype(np.int64)
        ab = d["arrival_bin"].astype(np.int64)
        j = lh.shape[1]
        if not (len(cutoff) == len(ab) == n):
            _fail(path, "entry arrays differ in length")
        if n and (cutoff.min() < 0 or cutoff.max() >= lh.shape[0]):
            _fail(path, "cutoff index outside lead_hours")
        if n and (nl.min() < 1 or nl.max() > j):
            _fail(path, "n_leads must be in 1..J")
        if n and ((ab < 0) | (ab > nl)).any():
            _fail(path, "arrival_bin must be in 0..n_leads")
        valid = np.arange(j)[None, :] < nl[:, None]
        elh = lh[cutoff]
        if not (np.isfinite(elh[valid]).all() and (elh[valid] > 0).all()):
            _fail(path, "lead_hours must be finite and > 0 on used leads")
        if j > 1:
            dl = np.diff(elh, axis=1)
            used = valid[:, 1:]
            if not (dl[used] > 0).all():
                _fail(path, "lead_hours must increase along used leads")
        for name in names:
            c = d[f"cdf_{name}"].astype(np.float64)
            if c.shape != (n, j):
                _fail(path, f"cdf_{name} must be N x J")
            cv = c[valid]
            if not (np.isfinite(cv).all() and ((cv >= 0) & (cv <= 1)).all()):
                _fail(path, f"cdf_{name} must be finite in [0, 1] on used leads")
            if j > 1:
                dc = np.diff(c, axis=1)[valid[:, 1:]]
                if (dc < -1e-12).any():
                    _fail(path, f"cdf_{name} must be nondecreasing in lead")
        jmax = max(jmax, j)
        raw.append((path.stem, nl, ab, elh, {k: d[f"cdf_{k}"].astype(np.float64) for k in names}))

    def pad(a):
        out = np.full((a.shape[0], jmax), np.nan)
        out[:, :a.shape[1]] = a
        return out

    return ArrivalEntries(
        fire=np.concatenate([np.full(len(r[1]), r[0]) for r in raw]),
        n_leads=np.concatenate([r[1] for r in raw]),
        arrival_bin=np.concatenate([r[2] for r in raw]),
        lead_hours=np.concatenate([pad(r[3]) for r in raw]),
        cdf={k: np.concatenate([pad(r[4][k]) for r in raw]) for k in names},
    )


def rps(e: ArrivalEntries, name: str) -> np.ndarray:
    j = e.lead_hours.shape[1]
    valid = np.arange(j)[None, :] < e.n_leads[:, None]
    observed = (e.arrival_bin[:, None] <= np.arange(j)[None, :]).astype(np.float64)
    sq = np.where(valid, (np.nan_to_num(e.cdf[name]) - observed) ** 2, 0.0)
    return sq.sum(axis=1)


def score_arrival(e: ArrivalEntries, *, draws: int = DRAWS, seed: int = SEED,
                  lead_edges=DEFAULT_HORIZON_EDGES_H, references=("persistence", "dilation_8h")) -> dict:
    fires = np.unique(e.fire)
    j = e.lead_hours.shape[1]
    valid = np.arange(j)[None, :] < e.n_leads[:, None]
    observed = (e.arrival_bin[:, None] <= np.arange(j)[None, :]).astype(np.float64)
    out = dict(entries=int(len(e.fire)), fires=fires.tolist(), models={}, paired={})
    per = {n: rps(e, n) for n in e.cdf}
    for name, r in per.items():
        rec = dict(mean_rps=float(r.mean()),
                   per_fire={str(f): float(r[e.fire == f].mean()) for f in fires}, by_lead=[])
        for lo, hi in zip(lead_edges[:-1], lead_edges[1:]):
            lh = e.lead_hours
            use = valid & (lh > lo) & (lh <= hi) if lo > 0 else valid & (lh >= lo) & (lh <= hi)
            n = int(use.sum())
            fires_in = int(len(np.unique(np.broadcast_to(e.fire[:, None], use.shape)[use]))) if n else 0
            rec["by_lead"].append(dict(lower=float(lo), upper=float(hi), cell_leads=n, fires=fires_in,
                                       positives=int(observed[use].sum()) if n else 0,
                                       brier=float(np.mean((e.cdf[name][use] - observed[use]) ** 2)) if n else None))
        out["models"][name] = rec
    rng_sample = np.random.default_rng(seed).integers(0, len(fires), size=(draws, len(fires)))
    counts = np.array([(e.fire == f).sum() for f in fires], dtype=np.float64)
    for name in per:
        for ref in references:
            if ref not in per or ref == name:
                continue
            sums = np.array([per[name][e.fire == f].sum() - per[ref][e.fire == f].sum() for f in fires])
            values = sums[rng_sample].sum(1) / counts[rng_sample].sum(1)
            lo, hi = np.quantile(values, [0.025, 0.975])
            out["paired"][f"{name}__vs__{ref}"] = dict(
                point_difference=float(sums.sum() / counts.sum()), percentile_95_interval=[float(lo), float(hi)],
                draws=draws, seed=seed, fires=len(fires),
                definition="candidate mean RPS minus reference; negative favours the candidate; whole fires resampled")
    return out
