"""Figures from suite evaluations (results/runs/suite_*/eval.json).

completeness_figure: detection completeness against ember SNR, one line per run or case.
case_errors_figure: per case, the main relative errors with the plan's goals as bands.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from wfglink.viz import style

GOALS = {"f1": 0.90, "track_speed_med_rel_err": 0.10, "cpc_gross_rel_err": 0.10, "exposure_rel_err": 0.10}


def _bin_centres(keys: list[str]) -> np.ndarray:
    out = []
    for k in keys:
        lo, hi = (float(t) for t in k.split("-"))
        out.append((lo + hi) / 2 if np.isfinite(hi) else lo * 1.25)
    return np.array(out)


def pooled_completeness(clips: list[dict]) -> dict[str, list[int]]:
    pooled: dict[str, list[int]] = {}
    for r in clips:
        for k, (h, n) in (r.get("completeness") or {}).items():
            acc = pooled.setdefault(k, [0, 0])
            acc[0] += h
            acc[1] += n
    return pooled


def completeness_figure(curves: dict[str, dict[str, list[int]]], path_stem: str | Path, title: str,
                        min_n: int = 30):
    """curves: label -> pooled {bin: [hits, n]}. Points with fewer than min_n embers are left out."""
    import matplotlib.pyplot as plt

    from scipy.stats import beta

    style.use()
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    for i, (label, bins) in enumerate(curves.items()):
        keys = [k for k, (h, n) in bins.items() if n >= min_n]
        if not keys:
            continue
        x = _bin_centres(keys)
        h = np.array([bins[k][0] for k in keys])
        n = np.array([bins[k][1] for k in keys])
        p = h / n
        lo = np.where(h > 0, beta.ppf(0.025, h, n - h + 1), 0.0)
        hi = np.where(h < n, beta.ppf(0.975, h + 1, n - h), 1.0)
        color = style.OKABE_ITO[(i + 1) % len(style.OKABE_ITO)]
        ax.errorbar(x, p, yerr=[p - lo, hi - p], marker="o", ms=3.5, lw=1.2, capsize=2, color=color, label=label)
    ax.axhline(0.5, color=style.COLORS["neutral"], lw=0.8, ls="--")
    ax.set_xscale("log")
    from matplotlib.ticker import FixedLocator, NullFormatter, NullLocator, ScalarFormatter

    ax.xaxis.set_major_locator(FixedLocator([3, 5, 10, 20, 30, 50, 100]))
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("Ember SNR (matched aperture, before compression)")
    ax.set_ylabel("Detection completeness (fraction)")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title(title)
    ax.legend(fontsize=8)
    return style.save(fig, path_stem)


def _missing_reason(row: dict, metric: str) -> str:
    """Why a case has no value: the exposure estimator declined, or no track or streak qualified."""
    if metric == "exposure_rel_err" and row.get("exposure_ok") == 0:
        return "declined"
    if metric in ("track_speed_med_rel_err", "streak_speed_med_rel_err"):
        return "no tracks"
    return "n/a"


def case_errors_figure(summary: dict[str, dict], path_stem: str | Path, title: str,
                       metrics: tuple[str, ...] = ("track_speed_med_rel_err", "cpc_gross_rel_err", "exposure_rel_err")):
    """Dot plot: rows are cases, one panel per metric (absolute relative error), goal shaded."""
    import matplotlib.pyplot as plt

    style.use()
    cases = list(summary)
    labels = {"track_speed_med_rel_err": "Track speed error", "cpc_gross_rel_err": "Count error (gate, gross)",
              "exposure_rel_err": "Exposure time error", "streak_speed_med_rel_err": "Streak speed error"}
    fig, axes = plt.subplots(1, len(metrics), figsize=(2.6 * len(metrics), 0.28 * len(cases) + 1.2), sharey=True)
    axes = np.atleast_1d(axes)
    y = np.arange(len(cases))
    for ax, m in zip(axes, metrics):
        v = np.array([abs(summary[c].get(m)) if summary[c].get(m) is not None else np.nan for c in cases])
        goal = GOALS.get(m)
        if goal is not None:
            ax.axvspan(0, goal, color=style.COLORS["goal"], alpha=0.12, lw=0)
        ax.plot(v, y, "o", ms=4, color=style.COLORS["track"])
        for yi, vi, c in zip(y, v, cases):
            if not np.isfinite(vi):
                ax.text(0.02, yi, _missing_reason(summary[c], m), va="center", fontsize=7,
                        color=style.COLORS["neutral"], transform=ax.get_yaxis_transform())
        ax.set_xlabel(f"{labels.get(m, m)} (abs, fraction)")
        ax.set_xlim(left=0)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(cases, fontsize=7)
    axes[0].invert_yaxis()
    fig.suptitle(title, fontsize=10)
    return style.save(fig, path_stem)


def load_eval(run_dir: str | Path) -> dict:
    return json.loads((Path(run_dir) / "eval.json").read_text())
