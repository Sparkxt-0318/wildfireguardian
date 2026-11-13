"""Native multi-observation cumulative marginals for the D2 candidates (A1 §5.2, revision 9).

A D2 candidate (d2_nll_rebuilt, d2_bracket_rebuilt) is a mean-field model evaluated by
``wildfire.survival.sample_forecast``. Its rollout already evolves the occupancy step by step
(``propagate_mean_field``), so the cumulative marginal P(newly burned by t_j | cutoff) at every later
survey t_j in the lead window is produced by ONE rollout whose step grid is broken exactly at each lead.
Nothing is refit and no extra model is used: this module runs ``sample_forecast`` UNCHANGED, swapping
only its step grid (``survival.step_durations``) for the multi-lead grid and capturing the full
``MeanFieldResult`` it computes. With a single lead it reproduces sample_forecast's endpoint exactly, and
at whole-hour leads every lead equals sample_forecast run to that lead (tested). A fractional lead adds an exact
break step there (the rollout's own step rule applied per segment), so a later lead can differ from a separate
sample_forecast run by that discretisation only.

Export: ``arrival_entries`` writes the sd9bench ``<fire>.npz`` contract (sd9bench/arrival.py):
cutoff, n_leads, arrival_bin, lead_hours (C, J) and cdf_<name> (N, J). Entries are cells unburned at their
cutoff that are valid in the forecast and in the score mask; a cell's arrival bin is the first later survey
whose state contains it, or n_leads if none.
"""
from __future__ import annotations

import contextlib
import math
from typing import Sequence

import numpy as np
import torch

LEAD_WINDOW_H = 48.0   # A1 §2: from each cutoff, every later observation time within 48 h


def lead_step_durations(leads: Sequence[float], base=None) -> list[float]:
    """Hourly steps with an exact break at every lead (each segment uses the rollout's own rule)."""
    if base is None:
        from wildfire.survival import step_durations as base
    leads = [float(x) for x in leads]
    if not leads or any(not math.isfinite(x) or x <= 0 for x in leads) or any(b <= a for a, b in zip(leads, leads[1:])):
        raise ValueError("leads must be finite, positive and strictly increasing")
    out, prev = [], 0.0
    for t in leads:
        out += base(t - prev)
        prev = t
    return out


@contextlib.contextmanager
def _multi_lead(leads):
    import wildfire.survival as SV
    captured = {}
    orig_steps, orig_prop = SV.step_durations, SV.propagate_mean_field

    def steps(hours):
        return lead_step_durations(leads, base=orig_steps)

    def prop(*a, **kw):
        res = orig_prop(*a, **kw)
        captured["result"] = res
        return res

    SV.step_durations, SV.propagate_mean_field = steps, prop
    try:
        yield captured
    finally:
        SV.step_durations, SV.propagate_mean_field = orig_steps, orig_prop


def cumulative_marginals(model, sample, leads: Sequence[float], info: dict | None = None, **kw):
    """Return (cdf [J, H, W], valid [J, H, W]) numpy arrays: P(newly burned by lead j) and validity.

    ``sample.hours`` is ignored for the step grid (the leads define it); everything else is sample_forecast.
    """
    from wildfire.survival import sample_forecast
    leads = [float(x) for x in leads]
    with _multi_lead(leads) as cap, torch.no_grad():
        sample_forecast(model, sample, **kw)
    res = cap["result"]
    cdf, val = [], []
    for t in leads:
        p, v = res.at(t)
        cdf.append(p[0, 0].detach().cpu().numpy().astype(np.float64))
        val.append(v[0, 0].detach().cpu().numpy().astype(bool))
    cdf = np.stack(cdf)
    # The cumulative new-burn occupancy is nondecreasing by construction; a decrease beyond float noise is an
    # error, not something to repair silently.
    drop = float(np.max(cdf[:-1] - cdf[1:])) if len(cdf) > 1 else 0.0
    if info is not None:
        info.update(max_decrease_raw=drop, min_raw=float(cdf.min()), max_raw=float(cdf.max()))
    if drop > 1e-6 or cdf.min() < -1e-6 or cdf.max() > 1 + 1e-6:
        raise ValueError(f"cumulative marginal not monotone in [0, 1] (max decrease {drop:.3g})")
    cdf = np.clip(np.maximum.accumulate(cdf, axis=0), 0.0, 1.0)
    return cdf, np.stack(val)


def arrival_entries(cutoffs, survey_hours, states, forecasts, score_mask=None, window=LEAD_WINDOW_H):
    """Build the sd9bench arrival arrays for one fire and one predictor.

    cutoffs: survey indices used as cutoffs; survey_hours: (K,) hours of every survey;
    states: (K, H, W) bool mapped-burned states; forecasts: {cutoff: (cdf [J_c, H, W], valid [J_c, H, W])}
    for that cutoff's leads (all later surveys within ``window`` h); score_mask: optional (H, W) bool.
    Returns dict with cutoff, n_leads, arrival_bin, lead_hours, cdf.
    """
    survey_hours = np.asarray(survey_hours, float)
    states = np.asarray(states, bool)
    leads_of = {}
    for c in cutoffs:
        later = [k for k in range(c + 1, len(survey_hours)) if 0 < survey_hours[k] - survey_hours[c] <= window]
        if later:
            leads_of[c] = later
    cut_list = sorted(leads_of)
    J = max(len(v) for v in leads_of.values())
    lead_hours = np.full((len(cut_list), J), np.nan)
    rows = dict(cutoff=[], n_leads=[], arrival_bin=[], cdf=[])
    for ci, c in enumerate(cut_list):
        ks = leads_of[c]
        lead_hours[ci, :len(ks)] = survey_hours[ks] - survey_hours[c]
        cdf, valid = forecasts[c]
        if cdf.shape[0] != len(ks):
            raise ValueError(f"cutoff {c}: forecast has {cdf.shape[0]} leads, expected {len(ks)}")
        cand = ~states[c] & valid.all(0)
        if score_mask is not None:
            cand &= score_mask
        idx = np.flatnonzero(cand.ravel())
        mapped = np.stack([states[k].ravel()[idx] for k in ks])          # (J_c, n)
        first = np.where(mapped.any(0), mapped.argmax(0), len(ks))
        f = np.full((len(idx), J), np.nan)
        f[:, :len(ks)] = cdf.reshape(len(ks), -1)[:, idx].T
        rows["cutoff"].append(np.full(len(idx), ci))
        rows["n_leads"].append(np.full(len(idx), len(ks)))
        rows["arrival_bin"].append(first)
        rows["cdf"].append(f)
    return dict(cutoff=np.concatenate(rows["cutoff"]).astype(np.int64),
                n_leads=np.concatenate(rows["n_leads"]).astype(np.int64),
                arrival_bin=np.concatenate(rows["arrival_bin"]).astype(np.int64),
                lead_hours=lead_hours, cdf=np.concatenate(rows["cdf"]))
