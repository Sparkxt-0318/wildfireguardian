"""Ember-derived air velocity field (plan section 3): a grid of cells over the picture.

Per cell and time window:
1. One sample per track: the mean per-point velocity (vx_poly, vy_poly) of that track's
   points inside the cell, so a slow ember that lingers does not outvote fast ones.
2. Outliers among the samples are removed per component beyond field.mad_k median absolute
   deviations (scaled to a standard deviation), but never within field.mad_floor_px_s.
3. The estimate is the median of the remaining samples.
4. Normalised median test against the 8 neighbours (Westerweel and Scarano 2005): a cell
   whose vector differs from its neighbours' median by more than
   field.normalized_median_threshold times their median residual (plus
   field.normalized_median_eps_px_s) is flagged and not shown.
5. Display status: fewer than field.min_tracks_show tracks hidden; up to
   field.min_tracks_ci - 1 shown hatched without an interval; from field.min_tracks_ci a
   bootstrap interval over tracks (field.bootstrap replicates) for u and v.

Embers are not air: the horizontal component is the wind proxy; the vertical component
includes settling and is biased downward (image y points down). Units are px/s.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _cfg(cfg: dict) -> dict:
    f = cfg.get("field", {})
    return {"grid": tuple(int(v) for v in f.get("grid", [16, 9])),
            "min_show": int(f.get("min_tracks_show", 5)), "min_ci": int(f.get("min_tracks_ci", 10)),
            "mad_k": float(f.get("mad_k", 3.0)), "mad_floor": float(f.get("mad_floor_px_s", 10.0)), "nmt_threshold": float(f.get("normalized_median_threshold", 2.0)),
            "nmt_eps": float(f.get("normalized_median_eps_px_s", 3.0)), "bootstrap": int(f.get("bootstrap", 200)),
            "ci": float(f.get("ci", 0.95))}


def track_cell_samples(points: pd.DataFrame, frame_size: tuple[int, int], grid: tuple[int, int]) -> pd.DataFrame:
    """One velocity sample per (cell, track): mean of the track's per-point velocities in the cell."""
    w, h = frame_size
    cols, rows = grid
    p = points[np.isfinite(points["vx_poly"]) & np.isfinite(points["vy_poly"])
               & np.isfinite(points["x_meas"]) & np.isfinite(points["y_meas"])]
    if "static" in p:
        p = p[~p["static"].astype(bool)]
    if len(p) == 0:
        return pd.DataFrame(columns=["row", "col", "track_id", "u", "v", "points"])
    c = np.clip((p["x_meas"].to_numpy() / w * cols).astype(int), 0, cols - 1)
    r = np.clip((p["y_meas"].to_numpy() / h * rows).astype(int), 0, rows - 1)
    d = pd.DataFrame({"row": r, "col": c, "track_id": p["track_id"].to_numpy(),
                      "u": p["vx_poly"].to_numpy(), "v": p["vy_poly"].to_numpy()})
    g = d.groupby(["row", "col", "track_id"], sort=True)
    out = g[["u", "v"]].mean()
    out["points"] = g.size()
    return out.reset_index()


def _mad_keep(x: np.ndarray, k: float, floor: float) -> np.ndarray:
    """Within k robust standard deviations of the median, but never closer than floor: with
    a dozen samples the MAD can come out far below the true spread and reject good tracks."""
    med = np.median(x)
    mad = 1.4826 * np.median(np.abs(x - med))
    return np.abs(x - med) <= max(k * mad, floor)


def normalized_median_test(u: np.ndarray, v: np.ndarray, valid: np.ndarray, threshold: float, eps: float) -> np.ndarray:
    """True where a valid vector fails the test against its valid 8-neighbours (needs 3 or more)."""
    rows, cols = u.shape
    bad = np.zeros_like(valid)
    for r in range(rows):
        for c in range(cols):
            if not valid[r, c]:
                continue
            nb = [(rr, cc) for rr in range(r - 1, r + 2) for cc in range(c - 1, c + 2)
                  if (rr, cc) != (r, c) and 0 <= rr < rows and 0 <= cc < cols and valid[rr, cc]]
            if len(nb) < 3:
                continue
            res = []
            for comp in (u, v):
                vals = np.array([comp[x] for x in nb])
                med = np.median(vals)
                rm = np.median(np.abs(vals - med))
                res.append(abs(comp[r, c] - med) / (rm + eps))
            if np.hypot(*res) > threshold:
                bad[r, c] = True
    return bad


def estimate_field(points: pd.DataFrame, frame_size: tuple[int, int], cfg: dict, seed: int = 0,
                   window: tuple[float, float] | None = None) -> pd.DataFrame:
    """One row per cell: u, v (px/s), tracks, status (hidden, hatched, ci, outlier) and intervals."""
    c = _cfg(cfg)
    cols, rows = c["grid"]
    if window is not None:
        points = points[(points["t"] >= window[0]) & (points["t"] < window[1])]
    s = track_cell_samples(points, frame_size, (cols, rows))
    rng = np.random.default_rng(seed)
    U = np.full((rows, cols), np.nan)
    V = np.full((rows, cols), np.nan)
    N = np.zeros((rows, cols), int)
    out = []
    groups = {k: g for k, g in s.groupby(["row", "col"])} if len(s) else {}
    for r in range(rows):
        for cc in range(cols):
            g = groups.get((r, cc))
            rec = {"row": r, "col": cc, "x_center": (cc + 0.5) * frame_size[0] / cols,
                   "y_center": (r + 0.5) * frame_size[1] / rows, "tracks": 0, "u": np.nan, "v": np.nan,
                   "u_lo": np.nan, "u_hi": np.nan, "v_lo": np.nan, "v_hi": np.nan, "status": "hidden"}
            if g is not None and len(g):
                u, v = g["u"].to_numpy(), g["v"].to_numpy()
                keep = _mad_keep(u, c["mad_k"], c["mad_floor"]) & _mad_keep(v, c["mad_k"], c["mad_floor"])
                u, v = u[keep], v[keep]
                n = int(u.size)
                rec["tracks"] = n
                if n:
                    rec["u"], rec["v"] = float(np.median(u)), float(np.median(v))
                    U[r, cc], V[r, cc], N[r, cc] = rec["u"], rec["v"], n
                if n >= c["min_ci"] and c["bootstrap"] > 0:
                    idx = rng.integers(0, n, size=(c["bootstrap"], n))
                    bu, bv = np.median(u[idx], axis=1), np.median(v[idx], axis=1)
                    a = (1 - c["ci"]) / 2
                    rec.update(u_lo=float(np.quantile(bu, a)), u_hi=float(np.quantile(bu, 1 - a)),
                               v_lo=float(np.quantile(bv, a)), v_hi=float(np.quantile(bv, 1 - a)), status="ci")
                elif n >= c["min_show"]:
                    rec["status"] = "hatched"
            out.append(rec)
    df = pd.DataFrame(out)
    shown = (N >= c["min_show"]) & np.isfinite(U)
    bad = normalized_median_test(U, V, shown, c["nmt_threshold"], c["nmt_eps"])
    flat_bad = bad.ravel()
    df.loc[flat_bad, "status"] = "outlier"
    return df


def field_errors(est: pd.DataFrame, truth: pd.DataFrame) -> dict[str, float]:
    """RMSE of shown cells against the true ember field and the true air field (px/s)."""
    m = est.merge(truth, on=["row", "col"], suffixes=("", "_t"))
    m = m[m["status"].isin(["hatched", "ci"]) & np.isfinite(m["u_median"])]
    if len(m) == 0:
        return {"cells": 0}
    du, dv = m["u"] - m["u_median"], m["v"] - m["v_median"]
    dua, dva = m["u"] - m["ua_median"], m["v"] - m["va_median"]
    ci = m[m["status"] == "ci"]
    cover = None
    if len(ci):
        cover = float(np.mean((ci["u_lo"] <= ci["u_median"]) & (ci["u_median"] <= ci["u_hi"])
                              & (ci["v_lo"] <= ci["v_median"]) & (ci["v_median"] <= ci["v_hi"])))
    return {"cells": int(len(m)), "rmse_ember_u": float(np.sqrt(np.mean(du ** 2))),
            "rmse_ember_v": float(np.sqrt(np.mean(dv ** 2))), "rmse_air_u": float(np.sqrt(np.mean(dua ** 2))),
            "rmse_air_v": float(np.sqrt(np.mean(dva ** 2))), "ci_cells": int(len(ci)), "ci_coverage_ember": cover}
