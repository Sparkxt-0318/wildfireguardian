"""External-reference evaluation against NIROPS surveys: stepwise reference time of arrival, per-survey Sorensen
coefficient, event score, and the paired statistics over events.
"""
import itertools
import numpy as np
from affine import Affine
from rasterio import features
from scipy.stats import binomtest, rankdata, spearmanr

CELL_M = 375.0
MARGIN_M = 2000.0
WINDOW = (0.01, 0.90)        # growth window: share of the final reference pixels, lower bound inclusive, upper exclusive


def reference_grid(bounds):
    """375 m EPSG:5070 grid covering the perimeter bounds plus 2 km, edges on multiples of 375 m."""
    x0, y0, x1, y1 = bounds
    gx0, gy1 = np.floor((x0 - MARGIN_M) / CELL_M) * CELL_M, np.ceil((y1 + MARGIN_M) / CELL_M) * CELL_M
    w, h = int(np.ceil((x1 + MARGIN_M - gx0) / CELL_M)), int(np.ceil((gy1 - (y0 - MARGIN_M)) / CELL_M))
    return Affine(CELL_M, 0, gx0, 0, -CELL_M, gy1), (h, w)


def reference_toa(survey_polygons, survey_hours, transform, shape):
    """Reference ToA: for each pixel, the time of the first survey whose cumulative burned area (union with all
    earlier surveys) encloses the pixel centre. NaN outside the final perimeter."""
    toa, covered = np.full(shape, np.nan, np.float32), np.zeros(shape, bool)
    for geom, t in sorted(zip(survey_polygons, survey_hours), key=lambda gt: gt[1]):
        inside = features.geometry_mask([geom], out_shape=shape, transform=transform, invert=True)
        toa[inside & ~covered] = t
        covered |= inside
    return toa


def event_sc(predicted, reference, survey_hours, window=WINDOW):
    """Event score: median over the surveys of the growth window of SC = 2H / (2H + M + F), where at survey time t
    the predicted burned set is {predicted <= t} and the reference set is {reference <= t}; rounded to four decimals.
    `predicted` and `reference` are 1-D arrays over the pixels inside the final reference perimeter."""
    n, scores = len(reference), []
    times = np.asarray(survey_hours, float)
    for t, t32 in zip(times, times.astype(np.float32)):
        ref = reference <= t32
        r = int(ref.sum())
        if max(1, window[0] * n) <= r < window[1] * n:
            pred = predicted.astype(float) <= t
            scores.append(2 * int((pred & ref).sum()) / (int(pred.sum()) + r))
    return round(float(np.median(scores)), 4), len(scores)


def paired_sign_tests(values, n_boot=10000, seed=20260906):
    """Two-sided exact sign tests for all pairs of configurations over events, Holm-adjusted within the family,
    with the median paired difference and its percentile bootstrap interval (events resampled)."""
    names = list(values); n = len(values[names[0]])
    idx = np.random.default_rng(seed).integers(0, n, size=(n_boot, n))
    out = {}
    for a, b in itertools.combinations(names, 2):
        d = np.asarray(values[b]) - np.asarray(values[a])
        wins, ties = int((d > 0).sum()), int((d == 0).sum())
        out[f"{b} - {a}"] = {"median_difference": float(np.median(d)), "ci95": np.quantile(np.median(d[idx], axis=1), [0.025, 0.975]).tolist(),
                             "wins": wins, "non_ties": n - ties, "p": float(binomtest(wins, n - ties).pvalue) if n > ties else 1.0}
    running = 0.0
    for rank, key in enumerate(sorted(out, key=lambda k: out[k]["p"])):
        running = max(running, min(1.0, (len(out) - rank) * out[key]["p"])); out[key]["holm_p"] = running
    return out


def spearman_with_interval(x, y, n_boot=10000, seed=20260906):
    """Spearman correlation over events with a percentile bootstrap interval (event pairs resampled)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    rho = spearmanr(x, y)
    idx = np.random.default_rng(seed).integers(0, len(x), size=(n_boot, len(x)))
    a, b = rankdata(x[idx], axis=1), rankdata(y[idx], axis=1)
    a -= a.mean(axis=1, keepdims=True); b -= b.mean(axis=1, keepdims=True)
    den = np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
    r = (a * b).sum(axis=1)[den > 0] / den[den > 0]
    return {"rho": float(rho.statistic), "p": float(rho.pvalue), "ci95": np.quantile(r, [0.025, 0.975]).tolist()}
