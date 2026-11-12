"""S-D9 scoring: forecast-v2 metrics, plus horizon and band strata and burned-area CRPS.

The pooled, per-fire and paired whole-fire scores call the maintained
``wildfire.baselines`` functions, so their definitions are identical to the
forecast-v2 canonical report. The paired BSS intervals repeat the logic of
``research/forecast-v2/scripts/report.py::detailed_scores``. The test suite
checks both against the committed RESULTS.json.

Additions, each reported as a separate block:
  by_horizon     the same pooled metrics within fixed horizon bins, with fire counts
  by_band        the same within fixed distance-to-cutoff-burn bands (needs dist_m)
  area_crps      ensemble CRPS of the per-interval new-burn cell count (needs
                 area_samples); otherwise reported as unavailable, never approximated
  base_rate_bss  1 - Brier / (pbar (1 - pbar)), with pbar the in-sample pooled
                 base rate. This is the Brier decomposition's uncertainty term,
                 a diagnostic and not a forecast.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_FORECAST = Path(__file__).resolve().parents[4] / "forecast"
if str(_FORECAST) not in sys.path:
    sys.path.insert(0, str(_FORECAST))

from wildfire import baselines as B  # noqa: E402

from .entries import HINDSIGHT_NOTE, Entries  # noqa: E402

SEED = 20261030
DRAWS = 10000
DEFAULT_HORIZON_EDGES_H = (0.0, 12.0, 24.0, 36.0, 48.0)
DEFAULT_BAND_EDGES_M = (0.0, 1000.0, 2000.0, 4000.0, 8000.0)
DEFAULT_CUMULATIVE_BANDS_M = (1000.0, 2000.0, 4000.0, 8000.0)
LOW_P_EDGES = (0.0, 1e-5, 1e-4, 1e-3, 1e-2, 0.1)
MC_FLOOR = 1.0 / 1024.0


def equal_fire_interval(entries, candidate, reference, draws: int = DRAWS, seed: int = SEED) -> dict:
    """Mean over fires of per-fire Brier differences (each fire weighted equally), whole-fire bootstrap."""
    fires = np.unique(entries.fire)
    per = np.array([np.mean((candidate[entries.fire == f] - entries.y[entries.fire == f]) ** 2)
                    - np.mean((reference[entries.fire == f] - entries.y[entries.fire == f]) ** 2) for f in fires])
    sampled = np.random.default_rng(seed).integers(0, len(fires), size=(draws, len(fires)))
    values = per[sampled].mean(axis=1)
    lo, hi = np.quantile(values, [0.025, 0.975])
    return dict(point_difference=float(per.mean()), percentile_95_interval=[float(lo), float(hi)],
                excludes_zero=bool(hi < 0 or lo > 0), draws=draws, seed=seed,
                definition="mean over fires of (candidate - reference) per-fire Brier; negative favours candidate")


def low_probability_bins(y: np.ndarray, p: np.ndarray, edges=LOW_P_EDGES) -> list[dict]:
    """Reliability within [lo, hi) for each low-probability bin; the last bin is [lo, hi)."""
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        use = (p >= lo) & (p < hi)
        n = int(use.sum())
        rows.append(dict(lower=float(lo), upper=float(hi), count=n, share=n / len(y) if len(y) else None,
                         positives=int(y[use].sum()), mean_prediction=float(p[use].mean()) if n else None,
                         observed_frequency=float(y[use].mean()) if n else None))
    return rows


def bss_intervals(entries: dict, scored: dict, references=("persistence", "dilation_best"),
                  draws: int = DRAWS, seed: int = SEED) -> None:
    """Add the exact NLL and the paired whole-fire BSS intervals in place (forecast-v2 report logic)."""
    fire, y = entries["fire"], entries["y"]
    fires = np.unique(fire)
    sampled = np.random.default_rng(seed).integers(0, len(fires), size=(draws, len(fires)))
    errors = {n: np.array([np.sum((p[fire == f] - y[fire == f]) ** 2) for f in fires])
              for n, p in entries["predictions"].items()}
    for name, record in scored["models"].items():
        p = entries["predictions"][name]
        wrong = int((((p == 0) & (y == 1)) | ((p == 1) & (y == 0))).sum())
        exact = None if wrong else float((-np.log(p[y == 1]).sum() - np.log1p(-p[y == 0]).sum()) / len(y))
        record["pooled"]["exact_nll"] = dict(value=exact, infinite=bool(wrong), certainty_wrong_entries=wrong)
        for reference in references:
            if reference not in errors:
                continue
            denominator = errors[reference].sum()
            metric = "bss_vs_" + ("best_dilation" if reference == "dilation_best" else reference)
            record["pooled"][metric] = float(1 - errors[name].sum() / denominator) if denominator else None
            resampled = errors[reference][sampled].sum(1)
            supported = resampled > 0
            values = 1 - errors[name][sampled].sum(1)[supported] / resampled[supported]
            interval = np.quantile(values, [.025, .975]).tolist() if len(values) else None
            record[metric + "_paired_fire_95_interval"] = dict(
                interval=interval, draws=draws, seed=seed, undefined_zero_reference_draws=int((~supported).sum()),
                unit="whole fire, pooled error ratio")
            for event, per_fire in record["per_fire"].items():
                db = scored["models"][reference]["per_fire"][event]["brier"]
                per_fire[metric] = 1 - per_fire["brier"] / db if db else None


def core(entries: Entries, references=("persistence", "dilation_best"), draws: int = DRAWS,
         seed: int = SEED) -> dict:
    """forecast-v2-identical pooled, per-fire and paired scores, plus base-rate BSS."""
    e = entries.as_baselines_entries()
    refs = tuple(r for r in references if r in entries.predictions)
    scored = B.score_entries(e, references=refs, draws=draws, seed=seed)
    bss_intervals(e, scored, references=refs, draws=draws, seed=seed)
    pbar = float(entries.y.mean()) if len(entries.y) else None
    for record in scored["models"].values():
        pooled = record["pooled"]
        unc = pbar * (1 - pbar) if pbar is not None else 0.0
        pooled["base_rate_bss"] = (1 - pooled["brier"] / unc) if unc else None
    for name, record in scored["models"].items():
        p = entries.predictions[name]
        record["pooled"]["low_probability_bins"] = low_probability_bins(entries.y, p)
        record["pooled"]["zero_probability_positive_share"] = (
            float(((p == 0) & (entries.y == 1)).sum() / entries.y.sum()) if entries.y.sum() else None)
        below = int(((p < MC_FLOOR) & (entries.y == 1)).sum())
        record["pooled"]["positives_below_1_over_1024"] = below
    for name in scored["models"]:
        for ref in refs:
            if ref != name:
                scored["paired"][f"{name}__vs__{ref}"]["equal_fire"] = equal_fire_interval(
                    entries, entries.predictions[name], entries.predictions[ref], draws=draws, seed=seed)
    scored["base_rate"] = pbar
    return scored


def stratified(entries: Entries, key: np.ndarray, edges, label: str) -> list[dict]:
    """Pooled metrics (no bootstrap) within (lo, hi] strata of ``key``; the first stratum is [lo, hi].

    Entries outside every stratum are counted in no stratum (see ``unstratified`` in ``score``).
    """
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        use = (key > lo) & (key <= hi) if lo > 0 else (key >= lo) & (key <= hi)
        sub = entries.subset(use)
        row = dict(stratum=label, lower=float(lo), upper=float(hi), entries=int(use.sum()),
                   positives=int(sub.y.sum()), fires=int(len(np.unique(sub.fire))),
                   intervals=int(len({(f, i) for f, i in zip(sub.fire.tolist(), sub.interval.tolist())})))
        if use.sum():
            row["models"] = {n: B.score(sub.y, p) for n, p in sub.predictions.items()}
            for n, m in row["models"].items():
                m["low_probability_bins"] = low_probability_bins(sub.y, sub.predictions[n])
                for ref in ("persistence", "dilation_best"):
                    if ref in sub.predictions:
                        rb = float(np.mean((sub.predictions[ref] - sub.y) ** 2))
                        m["bss_vs_" + ("best_dilation" if ref == "dilation_best" else ref)] = \
                            (1 - m["brier"] / rb) if rb else None
        else:
            row["models"] = None
        out.append(row)
    return out


def crps_ensemble(samples: np.ndarray, observed: float) -> float:
    """CRPS of an empirical ensemble: E|X - y| - 0.5 E|X - X'| (exact for the empirical distribution)."""
    x = np.sort(np.asarray(samples, dtype=np.float64))
    m = len(x)
    term1 = np.abs(x - observed).mean()
    # E|X - X'| over all ordered pairs = 2/m^2 * sum_i (2i - m - 1) x_(i), with i from 1 to m
    i = np.arange(1, m + 1)
    term2 = 2.0 * np.sum((2 * i - m - 1) * x) / (m * m)
    return float(term1 - 0.5 * term2)


def area_crps(entries: Entries) -> dict:
    out = {}
    for name in entries.predictions:
        per_fire = entries.area_samples.get(name)
        if per_fire is None:
            out[name] = dict(status="UNAVAILABLE_NO_AREA_SAMPLES")
            continue
        values = {f: [crps_ensemble(per_fire[f][k], entries.area_observed[f][k])
                      for k in range(len(entries.area_observed[f]))] for f in sorted(per_fire)}
        flat = [v for vs in values.values() for v in vs]
        out[name] = dict(status="SCORED", unit="new-burn cells", mean_crps=float(np.mean(flat)),
                         intervals=len(flat), per_fire_mean={f: float(np.mean(v)) for f, v in values.items()})
    return out


def score(entries: Entries, *, references=("persistence", "dilation_best"), draws: int = DRAWS, seed: int = SEED,
          horizon_edges=DEFAULT_HORIZON_EDGES_H, band_edges=DEFAULT_BAND_EDGES_M,
          cumulative_bands=DEFAULT_CUMULATIVE_BANDS_M, mc_trajectories: dict[str, int] | None = None) -> dict:
    """``mc_trajectories`` declares, per Monte Carlo predictor, the number of trajectories
    behind each marginal. For each one it adds the finite-trajectory corrected Brier
    used by forecast-v2: Brier - mean(p(1-p))/(n-1)."""
    result = core(entries, references=references, draws=draws, seed=seed)
    for name, n in (mc_trajectories or {}).items():
        if name not in entries.predictions or int(n) < 2:
            raise ValueError(f"mc_trajectories: unknown predictor or n < 2: {name}={n}")
        p = entries.predictions[name]
        pooled = result["models"][name]["pooled"]
        pooled["brier_mc_variance_corrected"] = float(pooled["brier"] - np.mean(p * (1 - p)) / (int(n) - 1))
        pooled["mc_trajectories"] = int(n)
    result["by_horizon"] = stratified(entries, entries.hours, horizon_edges, "horizon_hours")
    outside = int(((entries.hours < horizon_edges[0]) | (entries.hours > horizon_edges[-1])).sum())
    result["unstratified"] = dict(horizon_entries_outside_edges=outside)
    if entries.dist_m is None:
        result["by_band"] = dict(status="UNAVAILABLE_NO_DIST_M")
    else:
        result["by_band"] = stratified(entries, entries.dist_m, band_edges, "distance_to_cutoff_burn_m")
        result["cumulative_bands"] = {}
        for width in cumulative_bands:
            use = entries.dist_m <= width
            sub = entries.subset(use)
            result["cumulative_bands"][str(int(width))] = (
                core(sub, references=references, draws=draws, seed=seed) if use.any() and sub.y.sum() else
                dict(status="UNAVAILABLE_EMPTY_OR_NO_POSITIVES", entries=int(use.sum()), positives=int(sub.y.sum())))
        result["positives_beyond_last_band"] = int((entries.y[entries.dist_m > max(cumulative_bands)]).sum())
        scaled = np.maximum(1000.0, 4000.0 * entries.hours / 24.0)
        use = entries.dist_m <= scaled
        sub = entries.subset(use)
        result["horizon_scaled_band"] = dict(
            rule="dist_m <= max(1 km, 4 km * hours / 24)", entries=int(use.sum()), positives=int(sub.y.sum()),
            positives_outside=int(entries.y[~use].sum()),
            scores=core(sub, references=references, draws=draws, seed=seed) if use.any() and sub.y.sum() else None)
    if entries.in_domain is None:
        result["by_domain"] = dict(status="UNAVAILABLE_NO_IN_DOMAIN")
    else:
        result["by_domain"] = {}
        for label, mask in (("inside", entries.in_domain), ("outside", ~entries.in_domain)):
            sub = entries.subset(mask)
            result["by_domain"][label] = (
                core(sub, references=references, draws=draws, seed=seed) if mask.any() and sub.y.sum() else
                dict(status="UNAVAILABLE_EMPTY_OR_NO_POSITIVES", entries=int(mask.sum()), positives=int(sub.y.sum())))
    result["meta"] = entries.meta
    result["population"] = entries.population
    if entries.population == "hindsight_restricted":
        result["population_note"] = HINDSIGHT_NOTE
    result["area_crps"] = area_crps(entries)
    from .ensemble import area_ensemble_scores
    result["area_ensemble"] = area_ensemble_scores(entries, horizon_edges=horizon_edges)
    result["settings"] = dict(references=list(references), draws=draws, seed=seed,
                              horizon_edges_h=list(horizon_edges), band_edges_m=list(band_edges),
                              cumulative_bands_m=list(cumulative_bands), low_p_edges=list(LOW_P_EDGES),
                              calibration_bins=B.BINS.tolist(), log_floor=B.LOG_FLOOR)
    return result
