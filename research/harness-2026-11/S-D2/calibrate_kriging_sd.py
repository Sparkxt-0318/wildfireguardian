"""Calibration of the Choi et al. (2026) kriging SD against independent NIROPS brackets.

Question: is ``tau_i ~ Normal(mu_i, sd_i)`` (kriged mean and kriging SD from
satellite detections) a calibrated law for arrival time, as the soft labels
and any sd-aware likelihood would assume?

Independent reference: the forecast-v2 held-out survey rows
(``forecast/runs/20261030_perimeter_trained/execution_v3/heldout/<event>.npz``)
for the six US 2024 fires.  Each row is a cell unburned in the NIROPS mapped
extent at ``t1`` with outcome ``y`` = inside the mapped extent at
``t2 = t1 + hours``.  Their ``row``/``col`` index the Zenodo raster grid
(verified below by shape).  The kriging inputs are VIIRS/GOES detections, not
NIROPS perimeters; only the product's spatial domain (the final perimeter)
comes from NIROPS.

Per cell the tightest NIROPS bracket is ``L = max(t1 over rows, t2 over y=0
rows)`` and ``U = min(t2 over y=1 rows)`` (``U = inf`` if never mapped in
the scored intervals).  The interval-censored log-likelihood of a scale
``c`` (and shift ``b``) applied to the kriged law is

    l(c, b) = sum_i log[ Phi((U_i - mu_i - b) / (c sd_i)) - Phi((L_i - mu_i - b) / (c sd_i)) ].

A calibrated SD gives c close to 1 (with b close to 0).  We also report the
randomized PIT of the bracket under the unscaled law and the coverage of the
central 50/90% kriging intervals (a bracket "hits" an interval if they
intersect, which is conservative: a calibrated law gives hit rates at least
the nominal level).  Mapped extent is not flame arrival and survey times are
approximate; this is a reference, not ground truth.

    python calibrate_kriging_sd.py --rasters DIR/rasters_us --out results/kriging_sd_calibration.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import log_ndtr, ndtr

REPO = Path(__file__).resolve().parents[3]
HELDOUT = REPO / "forecast/runs/20261030_perimeter_trained/execution_v3/heldout"
EVENTS = ["ID-BOF-000683_Wapiti_Wapiti", "ID-BOF-000904_Goat", "ID-BOF-001080_Lava",
          "ID-SCF-240202_RedRock", "WA-SES-000173_Pioneer", "WY-BTF-002416_FishCreek"]


def read_raster(path):
    import rasterio
    with rasterio.open(path) as src:
        a = src.read(1, masked=True)
        tags = src.tags()
        return np.asarray(a.filled(np.nan), dtype=np.float64), tags, src.shape


def brackets(npz_path, t0):
    z = np.load(npz_path)
    t1 = np.array([(pd.Timestamp(str(s)) - t0).total_seconds() / 3600 for s in z["t1"]])
    t2 = t1 + z["hours"]
    iv, r, c, y = z["interval"], z["row"], z["col"], z["y"].astype(bool)
    a1, a2 = t1[iv], t2[iv]
    df = pd.DataFrame(dict(r=r, c=c, lo=np.where(y, a1, a2), hi=np.where(y, a2, np.inf), y=y))
    g = df.groupby(["r", "c"]).agg(lo=("lo", "max"), hi=("hi", "min"), pos=("y", "any")).reset_index()
    return g, len(z["t1"])


def interval_loglik(lo, hi, mu, sd):
    za, zb = (lo - mu) / sd, (hi - mu) / sd
    # log(Phi(zb) - Phi(za)) computed stably on whichever side is smaller.
    upper = za > 0
    a, b = np.where(upper, -zb, za), np.where(upper, -za, zb)
    lb, la = log_ndtr(b), log_ndtr(a)
    with np.errstate(divide="ignore", invalid="ignore"):
        return lb + np.log1p(-np.exp(np.minimum(la - lb, 0.0)))


def fit_scale(lo, hi, mu, sd, shift=False):
    def nll(x):
        c = np.exp(x[0])
        b = x[1] if shift else 0.0
        v = interval_loglik(lo, hi, mu + b, c * sd)
        return -np.sum(np.maximum(v, -745.0))
    x0 = [0.0, 0.0] if shift else [0.0]
    res = minimize(nll, x0, method="Nelder-Mead", options=dict(xatol=1e-6, fatol=1e-6, maxiter=4000))
    c = float(np.exp(res.x[0]))
    return dict(c=c, b_hours=float(res.x[1]) if shift else 0.0, nll=float(res.fun),
                nll_at_c1=float(nll([0.0, 0.0] if shift else [0.0])))


def profile_scale(lo, hi, mu, sd, grid=np.exp(np.linspace(np.log(0.5), np.log(5.0), 241))):
    """Profile NLL over the scale c (no shift) and the 95% likelihood-ratio interval.

    The interval treats cells as independent, so it is optimistic for
    spatially correlated kriging errors; the spread across fires is the more
    honest uncertainty.
    """
    nll = np.array([-np.sum(np.maximum(interval_loglik(lo, hi, mu, c * sd), -745.0)) for c in grid])
    best = int(np.argmin(nll))
    inside = grid[2 * (nll - nll[best]) <= 3.841458820694124]
    return dict(c_grid_best=float(grid[best]), lr95=[float(inside.min()), float(inside.max())],
                at_edge=bool(best in (0, len(grid) - 1)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rasters", type=Path, required=True, help="rasters_us directory of the Zenodo archive")
    ap.add_argument("--out", type=Path, default=Path("results/kriging_sd_calibration.json"))
    a = ap.parse_args(argv)
    rng = np.random.default_rng(20261112)
    per_event, pooled = {}, []
    for ev in EVENTS:
        mu, tags, shape = read_raster(a.rasters / f"{ev}_pswt_ok_toa.tif")
        sd, _, _ = read_raster(a.rasters / f"{ev}_pswt_ok_std.tif")
        t0 = pd.Timestamp(tags["t0_utc"])
        t0 = t0.tz_localize("UTC") if t0.tzinfo is None else t0.tz_convert("UTC")  # tag is UTC (README)
        g, n_int = brackets(HELDOUT / f"{ev}.npz", t0)
        assert g.r.max() < shape[0] and g.c.max() < shape[1], "held-out rows do not index the raster grid"
        m, s = mu[g.r, g.c], sd[g.r, g.c]
        valid = np.isfinite(m) & np.isfinite(s) & (s > 0)
        pos_outside = int((g.pos & ~valid).sum())
        lo, hi = g.lo.to_numpy()[valid], g.hi.to_numpy()[valid]
        m, s, pos = m[valid], s[valid], g.pos.to_numpy()[valid]
        Fa, Fb = ndtr((lo - m) / s), ndtr((hi - m) / s)
        pit = rng.uniform(Fa, Fb)
        cov = {}
        for level, z in (("50", 0.6744897501960817), ("90", 1.6448536269514722)):
            hit = (hi > m - z * s) & (lo < m + z * s)
            cov[level] = dict(all=float(hit.mean()), mapped=float(hit[pos].mean()))
        width = np.where(np.isfinite(hi), hi - lo, np.nan)
        rec = dict(survey_intervals=n_int, cells_with_rows=int(len(g)), cells_with_kriging=int(valid.sum()),
                   mapped_cells_with_kriging=int(pos.sum()), mapped_cells_without_kriging=pos_outside,
                   kriging_sd_hours_median=float(np.median(s)),
                   bracket_width_hours_median_mapped=float(np.nanmedian(width[pos])) if pos.any() else None,
                   mean_minus_bracket_mid_hours_median_mapped=float(np.median(m[pos] - 0.5 * (lo[pos] + hi[pos]))) if pos.any() else None,
                   pit_histogram_10=np.histogram(pit, bins=10, range=(0, 1))[0].tolist(),
                   pit_mapped_histogram_10=np.histogram(pit[pos], bins=10, range=(0, 1))[0].tolist(),
                   central_interval_hit_rate=cov,
                   scale_only=fit_scale(lo, hi, m, s), scale_and_shift=fit_scale(lo, hi, m, s, shift=True),
                   scale_profile=profile_scale(lo, hi, m, s),
                   bracket_over_sd_median_mapped=float(np.nanmedian(width[pos] / s[pos])) if pos.any() else None)
        per_event[ev] = rec
        pooled.append((lo, hi, m, s, pos))
        print(ev, json.dumps({k: rec[k] for k in ("cells_with_kriging", "mapped_cells_with_kriging",
                                                    "kriging_sd_hours_median", "bracket_width_hours_median_mapped",
                                                    "scale_only", "scale_profile", "bracket_over_sd_median_mapped")}))
    lo, hi, m, s, pos = (np.concatenate(x) for x in zip(*pooled))
    result = dict(
        reference="forecast-v2 held-out NIROPS survey rows, six US 2024 fires",
        product="Choi et al. 2026 PSwt-OK time of arrival and kriging SD (Zenodo 10.5281/zenodo.21788344)",
        per_event=per_event,
        across_fires_scale=dict(values=[per_event[e]["scale_only"]["c"] for e in EVENTS],
                                min=float(min(per_event[e]["scale_only"]["c"] for e in EVENTS)),
                                max=float(max(per_event[e]["scale_only"]["c"] for e in EVENTS)),
                                geometric_mean=float(np.exp(np.mean([np.log(per_event[e]["scale_only"]["c"]) for e in EVENTS])))),
        pooled=dict(cells=int(len(m)), mapped=int(pos.sum()),
                    scale_only=fit_scale(lo, hi, m, s), scale_profile=profile_scale(lo, hi, m, s), scale_and_shift=fit_scale(lo, hi, m, s, shift=True),
                    mapped_only_scale_and_shift=fit_scale(lo[pos], hi[pos], m[pos], s[pos], shift=True)))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=1))
    print("POOLED", json.dumps(result["pooled"]))


if __name__ == "__main__":
    main()
