#!/usr/bin/env python
"""What does the observed fire-spread direction follow? (Session 11)

Session 10 measured that the labels carry a clear direction (pooled R = 0.601)
and that ERA5's 28 km wind does not point at it (circular correlation -0.053,
mean gap 75.45 deg). This script does two things with that result.

PHASE 1 — harden it against the two confounders the follow-up flagged.

  1a. Wind time-averaging. A single ERA5 sample at step start was used to
      characterise a 6-16 h step. Three variants are now computed side by side:
      wind at step start (the Session 10 method), the VECTOR mean over the step
      (mean of u and v, then the bearing — averaging bearings directly is wrong
      for a circular quantity), and wind at the step midpoint. A supplementary
      fourth, the mean of UNIT wind vectors, separates "timing" from "speed
      weighting": it differs from the vector mean only in dropping the speed
      weight.

  1b. Row-set alignment. Session 10 used every newly-burnt cell. The model's
      positive rows additionally pass a 6,000 m buffer and a burnable filter.
      Both row sets are now computed for every quantity.

PHASE 2 — ask what the bearing DOES follow, using the DEM already in the repo.

  Upslope bearing, from the DEM gradient over the cells that newly burnt, at
  three smoothing windows. Fires run upslope; slope sits beside wind in
  Rothermel (1972), and terrain-driven channeling is the reason WindNinja
  exists (Forthofer, Butler & Wagenbrenner 2014, IJWF 23:969-981).

  Valley axis, from the structure tensor of the local elevation gradients. The
  eigenvector of the SMALLER eigenvalue of the gradient covariance points along
  the direction in which elevation changes least — the channel/ridge axis.
  ⚠ This is an AXIS, not a direction: it has no head or tail. Agreement with it
  is therefore folded to [0, 90] deg, where 45 deg is what chance gives, and
  correlation uses doubled angles (axial circular statistics). Reporting it on
  the same 0-180 scale as wind would silently flatter it.

CONSISTENCY CHECK. Under the Session 10 settings (all-cells row set, wind at
step start) this script must reproduce docs/label_geometry.json exactly. It
prints that comparison and exits non-zero on mismatch, because a hardening
analysis that quietly disagrees with what it is hardening is worthless.

    python scripts/direction_drivers.py --write

Writes docs/direction_drivers.json and docs/figures/direction_drivers_<fire>.png.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

OUT_JSON = REPO / "docs" / "direction_drivers.json"
FIGDIR = REPO / "docs" / "figures"
SESSION10 = REPO / "docs" / "label_geometry.json"

#: Reused verbatim from scripts/label_geometry.py. NOT a new criterion.
MIN_NEW_CELLS = 5

#: DEM smoothing windows for the upslope gradient, in metres. 0 = raw 500 m grid.
#: A curve rather than three points, because the first run showed the mean
#: angular difference moving 73 -> 70 -> 55 deg across 0/1500/3000 m. A result
#: that depends that strongly on a free parameter has to be shown depending on
#: it, and the far end has to be shown too: by 5 km the "upslope" of a 500 m
#: grid is a regional trend, not the slope a fire runs up.
#: ⚠ These are the TRUE window widths, not requested ones. A boxcar on a 500 m
#: grid can only be an odd number of cells, so a first attempt at
#: (0, 1000, 1500, 2000, 3000, 5000) silently collapsed 1000 and 1500 onto the
#: same 3-cell filter and reported them as two independent points with
#: identical values. These map exactly onto 1, 3, 5, 7 and 11 cells.
SMOOTH_WINDOWS_M = (0.0, 1500.0, 2500.0, 3500.0, 5500.0)

#: Neighbourhood over which the valley-axis structure tensor is accumulated.
VALLEY_WINDOW_M = 3000.0


# --------------------------------------------------------------------------
# circular helpers
# --------------------------------------------------------------------------


def bearing_of(east: float, north: float) -> float:
    """Compass bearing (deg) of a vector, matching weather.wind_toward_deg."""
    return float((np.degrees(np.arctan2(east, north)) + 360.0) % 360.0)


def mean_unit_bearing(east: np.ndarray, north: np.ndarray) -> tuple[float, float]:
    """(R, bearing) of a set of vectors, each normalised to unit length first."""
    norm = np.hypot(east, north)
    keep = norm > 1e-9
    if not keep.any():
        return float("nan"), float("nan")
    mx = float((east[keep] / norm[keep]).mean())
    my = float((north[keep] / norm[keep]).mean())
    return float(np.hypot(mx, my)), bearing_of(mx, my)


def ang_diff(a: float, b: float) -> float:
    """Directional difference, 0-180 deg. 90 is what unrelated bearings give."""
    return float(abs((a - b + 180.0) % 360.0 - 180.0))


def axial_diff(a: float, b: float) -> float:
    """AXIAL difference, 0-90 deg. 45 is what an unrelated axis gives."""
    d = ang_diff(a, b)
    return float(min(d, 180.0 - d))


def circ_corr(alpha_deg, beta_deg, axial: bool = False) -> float | None:
    """Jammalamadaka-Sarma circular correlation. Doubles angles when axial."""
    a = np.radians(np.asarray(alpha_deg, dtype=float))
    b = np.radians(np.asarray(beta_deg, dtype=float))
    if len(a) < 3:
        return None
    if axial:
        a, b = 2.0 * a, 2.0 * b
    abar = np.arctan2(np.sin(a).mean(), np.cos(a).mean())
    bbar = np.arctan2(np.sin(b).mean(), np.cos(b).mean())
    num = float(np.sum(np.sin(a - abar) * np.sin(b - bbar)))
    den = float(np.sqrt(np.sum(np.sin(a - abar) ** 2) * np.sum(np.sin(b - bbar) ** 2)))
    return None if den == 0 else num / den


# --------------------------------------------------------------------------
# terrain
# --------------------------------------------------------------------------


def fill_nan_nearest(z: np.ndarray) -> np.ndarray:
    """Replace DEM nodata with the nearest valid elevation.

    ⚠ Necessary, and it changes results. The SRTM grids carry 0-2.8 % nodata
    (yeongdeok_2025 2.80 %, hongseong_2023 1.19 %, miryang_2022 1.15 %,
    uljin_samcheok_2022 0.00 %) over water and at the tile edge. A boxcar
    smooth spreads each NaN across its whole window, and the first run of this
    script lost 3 of 36 steps to that spread — the upslope bearing came back
    undefined for every cell in them. Nearest-valid fill is the mildest repair
    that keeps the gradient defined; it invents no topography beyond extending
    the nearest real value, and it only matters within a smoothing window of a
    nodata patch.
    """
    bad = ~np.isfinite(z)
    if not bad.any():
        return z.astype("float64")
    from scipy.ndimage import distance_transform_edt

    _, (ir, ic) = distance_transform_edt(bad, return_indices=True)
    return z.astype("float64")[ir, ic]


def upslope_field(elev: np.ndarray, cell_m: float, smooth_m: float):
    """(east, north) components of the steepest-ASCENT direction per cell."""
    from scipy.ndimage import uniform_filter

    z = fill_nan_nearest(elev)
    if smooth_m > 0:
        size = max(1, int(round(smooth_m / cell_m)))
        if size % 2 == 0:
            size += 1
        z = uniform_filter(z, size=size, mode="nearest")
    # row index increases southward, so d/dnorth = -d/drow.
    d_north = -np.gradient(z, cell_m, axis=0)
    d_east = np.gradient(z, cell_m, axis=1)
    return d_east, d_north


def valley_axis(elev: np.ndarray, cell_m: float, rows: np.ndarray, cols: np.ndarray,
                window_m: float = VALLEY_WINDOW_M) -> tuple[float, float]:
    """Local channel/ridge AXIS bearing over a set of cells, plus its anisotropy.

    Structure tensor of the elevation gradient, accumulated over the cells and
    their neighbourhood. The eigenvector of the SMALLER eigenvalue is the
    direction of least elevation change: along a valley floor or along a ridge
    crest. Returns (axis_bearing_deg in [0,180), anisotropy in [0,1]).

    Assumptions, stated because they are load-bearing:
      * a valley and a ridge with the same orientation are indistinguishable
        here — this is an axis, not a flow direction;
      * it describes the terrain under the newly-burnt cells, not a basin-scale
        drainage network, so it is local channeling and not catchment geometry;
      * anisotropy near 0 means the local terrain has no preferred axis and the
        bearing is meaningless.
    """
    from scipy.ndimage import uniform_filter

    size = max(1, int(round(window_m / cell_m)))
    if size % 2 == 0:
        size += 1
    z = uniform_filter(fill_nan_nearest(elev), size=3, mode="nearest")
    gn = -np.gradient(z, cell_m, axis=0)
    ge = np.gradient(z, cell_m, axis=1)

    jee = uniform_filter(ge * ge, size=size, mode="nearest")[rows, cols]
    jnn = uniform_filter(gn * gn, size=size, mode="nearest")[rows, cols]
    jen = uniform_filter(ge * gn, size=size, mode="nearest")[rows, cols]

    a, b, c = float(jee.mean()), float(jnn.mean()), float(jen.mean())
    tr = a + b
    if tr <= 1e-15:
        return float("nan"), 0.0
    disc = float(np.sqrt(max(0.0, (a - b) ** 2 + 4.0 * c * c)))
    lam_hi, lam_lo = 0.5 * (tr + disc), 0.5 * (tr - disc)
    # Eigenvector of the SMALLER eigenvalue -> least elevation change.
    ve, vn = (c, lam_lo - a) if abs(c) > 1e-15 else ((0.0, 1.0) if a > b else (1.0, 0.0))
    axis = bearing_of(ve, vn) % 180.0
    aniso = float((lam_hi - lam_lo) / tr) if tr > 0 else 0.0
    return axis, aniso


# --------------------------------------------------------------------------
# wind variants
# --------------------------------------------------------------------------


def wind_variants(ws, t0, t1) -> dict:
    """Bearings for the four wind samplings, plus how many samples backed each."""
    if ws is None:
        return {}
    import pandas as pd

    speed = np.asarray(ws.wind_speed_ms, dtype="float64")
    u = np.asarray(ws.wind_u, dtype="float64") * speed      # recover ERA5 u10
    v = np.asarray(ws.wind_v, dtype="float64") * speed      # recover ERA5 v10
    times = pd.DatetimeIndex(ws.time)

    out = {"wind_start_deg": float(ws.at(t0)["wind_toward_deg"])}
    mid = t0 + (t1 - t0) / 2
    out["wind_mid_deg"] = float(ws.at(mid)["wind_toward_deg"])

    inside = (times >= t0) & (times <= t1)
    n = int(inside.sum())
    out["n_wind_samples_in_step"] = n
    if n == 0:
        # Step shorter than the ERA5 cadence: fall back to the nearest sample and
        # SAY SO rather than silently reporting a mean of nothing.
        out["wind_vector_mean_deg"] = out["wind_start_deg"]
        out["wind_unit_mean_deg"] = out["wind_start_deg"]
        out["vector_mean_fell_back_to_nearest"] = True
        return out

    out["vector_mean_fell_back_to_nearest"] = False
    out["wind_vector_mean_deg"] = bearing_of(float(u[inside].mean()),
                                             float(v[inside].mean()))
    nrm = np.hypot(u[inside], v[inside])
    keep = nrm > 1e-9
    if keep.any():
        out["wind_unit_mean_deg"] = bearing_of(
            float((u[inside][keep] / nrm[keep]).mean()),
            float((v[inside][keep] / nrm[keep]).mean()))
    else:
        out["wind_unit_mean_deg"] = out["wind_vector_mean_deg"]
    out["wind_speed_mean_ms"] = round(float(speed[inside].mean()), 3)
    return out


WIND_KEYS = (("start", "wind_start_deg"),
             ("vector_mean", "wind_vector_mean_deg"),
             ("midpoint", "wind_mid_deg"),
             ("unit_mean", "wind_unit_mean_deg"))


# --------------------------------------------------------------------------
# per-fire analysis
# --------------------------------------------------------------------------


def model_positive_cells(fire_ids: list[str]) -> dict:
    """{(fire_id, op_index): (rows, cols)} for the model's POSITIVE rows only."""
    from wildfireguardian.spread_v2.features import build_dataset

    ds = build_dataset(fire_ids)
    pos = ds[ds["label"] == 1]
    out: dict = {}
    for (fid, op), grp in pos.groupby(["fire_id", "op_from"], sort=False):
        out[(str(fid), int(op))] = (grp["row"].to_numpy(), grp["col"].to_numpy())
    return out


def geometry_for_cells(rows, cols, active, cell_m) -> dict:
    """R and bearing in both reference frames, plus the advance ratio."""
    from scipy.ndimage import distance_transform_edt

    ar, ac = np.nonzero(active)
    c_r, c_c = float(ar.mean()), float(ac.mean())
    e_cen = (cols - c_c) * cell_m
    n_cen = (c_r - rows) * cell_m
    R_cen, bear_cen = mean_unit_bearing(e_cen, n_cen)

    _, (sr, sc) = distance_transform_edt(~active, return_indices=True)
    e_per = (cols - sc[rows, cols]) * cell_m
    n_per = (sr[rows, cols] - rows) * cell_m
    R_per, bear_per = mean_unit_bearing(e_per, n_per)

    th = np.radians(bear_cen)
    ux, uy = np.sin(th), np.cos(th)
    along = np.abs(e_cen * ux + n_cen * uy)
    across = np.abs(e_cen * (-uy) + n_cen * ux)
    p90a, p90c = float(np.percentile(along, 90)), float(np.percentile(across, 90))
    return {
        "n_cells": int(len(rows)),
        "R_centroid": round(R_cen, 6), "bearing_centroid_deg": round(bear_cen, 2),
        "R_perimeter": round(R_per, 6), "bearing_perimeter_deg": round(bear_per, 2),
        "advance_ratio_along_over_across": round(p90a / p90c, 4) if p90c > 1e-9 else None,
    }


def analyse_fire(fid: str, model_pos: dict, slope_field: np.ndarray | None = None) -> dict:
    """One fire's per-step geometry.

    ``slope_field`` overrides the per-cell slope used for ``mean_slope_deg``
    and therefore for slope stratification. It changes NOTHING else — bearings,
    upslope directions and the valley axis are untouched. Default None keeps
    the 500 m-baseline slope, so the committed artifact regenerates identically
    and the Session 10 consistency check still passes.
    """
    from wildfireguardian.spread_v2 import data as datamod
    from wildfireguardian.spread_v2 import grid as gridmod
    from wildfireguardian.spread_v2.weather import weather_series_from_event

    ev = datamod.load_event(fid)
    g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=gridmod.DEFAULT_CELL_M)
    snaps = gridmod.overpass_snapshots(ev, g, gap_minutes=90.0)
    ws = weather_series_from_event(ev)
    cs = g.cell_size_m

    elev = gridmod.elevation_on_grid(ev, g)
    slope = gridmod.slope_deg(elev, cs) if slope_field is None else slope_field
    upslope = {w: upslope_field(elev, cs, w) for w in SMOOTH_WINDOWS_M}

    steps = []
    for k in range(len(snaps) - 1):
        cur, nxt = snaps[k], snaps[k + 1]
        active = cur.cumulative_mask
        new = nxt.cumulative_mask & ~active
        n_new = int(new.sum())
        rec = {"step": k, "dt_hours": round(
            (nxt.time - cur.time).total_seconds() / 3600.0, 3),
            "n_new_cells": n_new, "usable": False}
        # SAME criterion as scripts/label_geometry.py. Not a new one.
        if n_new < MIN_NEW_CELLS or not active.any():
            steps.append(rec)
            continue
        rec["usable"] = True

        rows_all, cols_all = np.nonzero(new)
        cells = {"all": (rows_all, cols_all)}
        mp = model_pos.get((fid, int(cur.index)))
        if mp is not None and len(mp[0]) > 0:
            cells["model"] = mp

        rec["wind"] = wind_variants(ws, cur.time, nxt.time)
        rec["rowsets"] = {}
        for name, (rr, cc) in cells.items():
            geo = geometry_for_cells(rr, cc, active, cs)
            geo["mean_slope_deg"] = round(float(slope[rr, cc].mean()), 3)
            for w, (ge, gn) in upslope.items():
                R_up, b_up = mean_unit_bearing(ge[rr, cc], gn[rr, cc])
                geo[f"upslope_R_smooth{int(w)}"] = round(R_up, 6)
                geo[f"upslope_bearing_smooth{int(w)}_deg"] = round(b_up, 2)
                geo[f"obs_vs_upslope_smooth{int(w)}_deg"] = round(
                    ang_diff(geo["bearing_centroid_deg"], b_up), 2)
            ax, aniso = valley_axis(elev, cs, rr, cc)
            geo["valley_axis_deg"] = round(ax, 2)
            geo["valley_anisotropy"] = round(aniso, 6)
            geo["obs_vs_valley_axial_deg"] = round(
                axial_diff(geo["bearing_centroid_deg"], ax), 2)
            for label, key in WIND_KEYS:
                if key in rec["wind"]:
                    geo[f"obs_vs_wind_{label}_deg"] = round(
                        ang_diff(geo["bearing_centroid_deg"], rec["wind"][key]), 2)
            rec["rowsets"][name] = geo
        steps.append(rec)

    return {"fire_id": fid, "n_overpasses": len(snaps), "n_steps": len(steps),
            "n_usable_steps": sum(1 for s in steps if s["usable"]), "steps": steps}


# --------------------------------------------------------------------------
# aggregation
# --------------------------------------------------------------------------


def _agg(vals: list[float]) -> dict:
    v = np.asarray([x for x in vals if x is not None and not np.isnan(x)], dtype=float)
    if not len(v):
        return {"n": 0, "mean": None, "sd": None}
    return {"n": int(len(v)), "mean": round(float(v.mean()), 4),
            "sd": round(float(v.std(ddof=1)), 4) if len(v) > 1 else None}


def _driver_keys() -> list[str]:
    return ([f"wind_{lbl}" for lbl, _ in WIND_KEYS]
            + [f"upslope_smooth{int(w)}" for w in SMOOTH_WINDOWS_M])


def _step_rows(fire: dict, rowset: str) -> list[dict]:
    """Usable steps of one fire that have this row set, in order."""
    return [s for s in fire["steps"]
            if s["usable"] and rowset in s.get("rowsets", {})]


def _driver_bearing(step: dict, rowset: str, key: str) -> float | None:
    """The comparison bearing for one driver on one step."""
    if key.startswith("wind_"):
        wkey = dict(WIND_KEYS).get(key[len("wind_"):])
        return step["wind"].get(wkey) if wkey else None
    if key.startswith("upslope_smooth"):
        w = key[len("upslope_smooth"):]
        return step["rowsets"][rowset].get(f"upslope_bearing_smooth{w}_deg")
    return None


def _driver_angle(step: dict, rowset: str, key: str) -> float | None:
    g = step["rowsets"][rowset]
    if key.startswith("wind_"):
        return g.get(f"obs_vs_{key}_deg")
    if key.startswith("upslope_smooth"):
        return g.get(f"obs_vs_{key}_deg")
    return None


def _rounded(x, nd=4):
    return round(x, nd) if x is not None else None


def summarise(fires: list[dict], rowset: str) -> dict:
    """Pooled + fold-level summary for one row set."""
    keys = _driver_keys()
    obs, per_fire = [], {}
    drivers = {k: [] for k in keys}
    bearings = {k: [] for k in keys}
    valley_ax, valley_obs, R_list, slope_list, aniso = [], [], [], [], []

    for f in fires:
        us = _step_rows(f, rowset)
        if not us:
            continue
        fobs = [s["rowsets"][rowset]["bearing_centroid_deg"] for s in us]
        obs.extend(fobs)
        R_list.extend(s["rowsets"][rowset]["R_centroid"] for s in us)
        slope_list.extend(s["rowsets"][rowset]["mean_slope_deg"] for s in us)
        aniso.extend(s["rowsets"][rowset]["valley_anisotropy"] for s in us)
        fvax = [s["rowsets"][rowset]["valley_axis_deg"] for s in us]
        fvobs = [s["rowsets"][rowset]["obs_vs_valley_axial_deg"] for s in us]
        valley_ax.extend(fvax); valley_obs.extend(fvobs)

        f_angle, f_corr = {}, {}
        for k in keys:
            ang = [_driver_angle(s, rowset, k) for s in us]
            bea = [_driver_bearing(s, rowset, k) for s in us]
            ang = [a for a in ang if a is not None]
            bea_ok = [(o, b) for o, b in zip(fobs, bea) if b is not None]
            drivers[k].extend(ang)
            bearings[k].extend(b for _, b in bea_ok)
            f_angle[k] = _agg(ang)["mean"]
            f_corr[k] = _rounded(circ_corr([o for o, _ in bea_ok],
                                           [b for _, b in bea_ok])) \
                if len(bea_ok) >= 3 else None

        per_fire[f["fire_id"]] = {
            "n_usable_steps": len(us),
            "n_cells_median": int(np.median(
                [s["rowsets"][rowset]["n_cells"] for s in us])),
            "R_centroid": _agg([s["rowsets"][rowset]["R_centroid"] for s in us]),
            "mean_slope_deg": _agg([s["rowsets"][rowset]["mean_slope_deg"] for s in us]),
            "mean_abs_angle": f_angle,
            "circ_corr": f_corr,
            "valley_axial_mean_deg": _agg(fvobs)["mean"],
            "valley_circ_corr_axial": _rounded(circ_corr(fobs, fvax, axial=True))
            if len(fobs) >= 3 else None,
        }

    pooled = {
        "n_usable_steps": len(obs),
        "R_centroid": _agg(R_list),
        "mean_slope_deg": _agg(slope_list),
        "valley_anisotropy": _agg(aniso),
        "drivers": {},
        "valley_axis": {
            "mean_abs_axial_deg": _agg(valley_obs)["mean"],
            "sd": _agg(valley_obs)["sd"],
            "circ_corr_axial": _rounded(circ_corr(obs, valley_ax, axial=True)),
            "chance_level_deg": 45.0,
            "note": "AXIAL: 0-90 deg scale, chance is 45. Not comparable to the "
                    "0-180 directional scale the wind and upslope rows use.",
        },
    }
    for k in keys:
        pooled["drivers"][k] = {
            "mean_abs_angle_deg": _agg(drivers[k])["mean"],
            "sd_deg": _agg(drivers[k])["sd"],
            "n": _agg(drivers[k])["n"],
            "circ_corr": _rounded(circ_corr(obs, bearings[k])),
            "chance_level_deg": 90.0,
        }

    pooled["fold_spread_of_mean_angle"] = {
        k: _agg([pf["mean_abs_angle"][k] for pf in per_fire.values()
                 if pf["mean_abs_angle"].get(k) is not None]) for k in keys}
    pooled["fold_spread_of_circ_corr"] = {
        k: _agg([pf["circ_corr"][k] for pf in per_fire.values()
                 if pf["circ_corr"].get(k) is not None]) for k in keys}
    return {"pooled": pooled, "per_fire": per_fire}


def persistence(fires: list[dict], rowset: str) -> dict:
    a, b, d = [], [], []
    for f in fires:
        us = [s for s in f["steps"]
              if s["usable"] and rowset in s.get("rowsets", {})]
        for x, y in zip(us[:-1], us[1:]):
            if y["step"] != x["step"] + 1:
                continue
            ba = x["rowsets"][rowset]["bearing_centroid_deg"]
            bb = y["rowsets"][rowset]["bearing_centroid_deg"]
            a.append(ba); b.append(bb); d.append(ang_diff(ba, bb))
    return {
        "n_consecutive_step_pairs": len(a),
        "pooled_circ_corr": (lambda x: round(x, 4) if x is not None else None)(
            circ_corr(a, b)),
        "mean_abs_bearing_change_deg": round(float(np.mean(d)), 2) if d else None,
        "interpretation": (
            "NOT observable at this cadence rather than absent: a continuously "
            "curving front sampled every 6-16 h produces large apparent bearing "
            "jumps even under perfectly persistent spread."),
    }


def effective_windows(cell_m: float = 500.0) -> dict:
    """Requested window -> the odd cell count a boxcar actually uses."""
    out = {}
    for w in SMOOTH_WINDOWS_M:
        if w <= 0:
            out[str(int(w))] = {"cells": 1, "effective_m": cell_m}
            continue
        size = max(1, int(round(w / cell_m)))
        if size % 2 == 0:
            size += 1
        out[str(int(w))] = {"cells": size, "effective_m": size * cell_m}
    return out


def slope_conditioning(fires: list[dict], rowset: str, smooth: float = 1500.0) -> dict:
    """Does observed-vs-upslope agreement improve where the terrain is steep?"""
    pairs = []
    for f in fires:
        for s in f["steps"]:
            if not s["usable"] or rowset not in s.get("rowsets", {}):
                continue
            g = s["rowsets"][rowset]
            pairs.append((g["mean_slope_deg"],
                          g[f"obs_vs_upslope_smooth{int(smooth)}_deg"]))
    pairs = [(s, a) for s, a in pairs
             if s is not None and a is not None
             and np.isfinite(s) and np.isfinite(a)]
    if len(pairs) < 6:
        return {"n": len(pairs), "note": "too few usable steps to stratify"}
    sl = np.array([p[0] for p in pairs]); ang = np.array([p[1] for p in pairs])
    med = float(np.median(sl))
    lo, hi = sl <= med, sl > med
    terciles = []
    order = np.argsort(sl)
    for i, chunk in enumerate(np.array_split(order, 3)):
        terciles.append({"tercile": i + 1,
                         "slope_range_deg": [round(float(sl[chunk].min()), 2),
                                             round(float(sl[chunk].max()), 2)],
                         "n": int(len(chunk)),
                         "mean_abs_angle_deg": round(float(ang[chunk].mean()), 2)})
    # WITHIN-FIRE control. The steep half is largely one fire's steps
    # (uljin_samcheok_2022 supplies 17 of 36), so a pooled slope effect could be
    # "uljin agrees well and uljin is steep" rather than "steep terrain steers".
    # If the pattern survives inside a single fire it is a slope effect; if it
    # does not, it is fire identity wearing a slope costume.
    within = {}
    for f in fires:
        us = [s for s in f["steps"]
              if s["usable"] and rowset in s.get("rowsets", {})]
        pr = [(s["rowsets"][rowset]["mean_slope_deg"],
               s["rowsets"][rowset][f"obs_vs_upslope_smooth{int(smooth)}_deg"])
              for s in us]
        pr = [(a, b) for a, b in pr
              if a is not None and b is not None and np.isfinite(a) and np.isfinite(b)]
        if len(pr) < 6:
            within[f["fire_id"]] = {"n": len(pr), "note": "too few usable steps"}
            continue
        s_ = np.array([p[0] for p in pr]); a_ = np.array([p[1] for p in pr])
        m_ = float(np.median(s_))
        within[f["fire_id"]] = {
            "n": len(pr), "median_slope_deg": round(m_, 2),
            "gentler_half_mean_angle_deg": round(float(a_[s_ <= m_].mean()), 2),
            "steeper_half_mean_angle_deg": round(float(a_[s_ > m_].mean()), 2),
            "corr_slope_vs_angle": round(float(np.corrcoef(s_, a_)[0, 1]), 4),
        }

    return {
        "smoothing_m": smooth, "n": len(pairs),
        "median_slope_deg": round(med, 2),
        "within_fire_control": within,
        "gentler_half": {"n": int(lo.sum()),
                         "mean_abs_angle_deg": round(float(ang[lo].mean()), 2)},
        "steeper_half": {"n": int(hi.sum()),
                         "mean_abs_angle_deg": round(float(ang[hi].mean()), 2)},
        "terciles": terciles,
        "corr_slope_vs_angle": round(float(np.corrcoef(sl, ang)[0, 1]), 4),
        "reading": ("A NEGATIVE correlation means agreement improves as terrain "
                    "steepens, which is the physical consistency check."),
    }


# --------------------------------------------------------------------------
# consistency against Session 10
# --------------------------------------------------------------------------


def session10_check(fires: list[dict]) -> dict:
    """Under Session 10's settings this must reproduce Session 10's numbers."""
    if not SESSION10.exists():
        return {"ran": False, "reason": "docs/label_geometry.json absent"}
    s10 = json.loads(SESSION10.read_text(encoding="utf-8"))
    here = summarise(fires, "all")["pooled"]
    pers = persistence(fires, "all")
    checks = {
        "R_centroid_mean": (s10["pooled"]["R_centroid_mean"], here["R_centroid"]["mean"]),
        "circ_corr_obs_vs_wind": (s10["pooled"]["circ_corr_obs_vs_wind"],
                                  here["drivers"]["wind_start"]["circ_corr"]),
        "mean_abs_angle_obs_vs_wind_deg": (
            s10["pooled"]["mean_abs_angle_obs_minus_wind_deg"],
            here["drivers"]["wind_start"]["mean_abs_angle_deg"]),
        "n_usable_steps": (s10["pooled"]["n_usable_steps"], here["n_usable_steps"]),
        "bearing_persistence": (s10["bearing_persistence"]["pooled_circ_corr"],
                                pers["pooled_circ_corr"]),
        "mean_abs_bearing_change_deg": (
            s10["bearing_persistence"]["mean_abs_bearing_change_deg"],
            pers["mean_abs_bearing_change_deg"]),
    }
    def decimals(x) -> int:
        s = repr(float(x))
        return len(s.split(".")[1]) if "." in s else 0

    rows, ok = {}, True
    for k, (a, b) in checks.items():
        if isinstance(a, int) and isinstance(b, int):
            same = a == b
            shown = b
        elif a is None or b is None:
            same, shown = False, b
        else:
            # Both sides are stored ROUNDED, at different precisions. Compare at
            # the COARSER one, otherwise 0.601063 vs 0.6011 reads as drift when
            # it is the same value seen through two roundings.
            nd = min(decimals(a), decimals(b))
            shown = round(float(b), nd)
            same = abs(shown - round(float(a), nd)) <= 10 ** (-nd) / 2
        rows[k] = {"session10": a, "session11": b, "session11_rounded": shown,
                   "matches": bool(same)}
        ok = ok and same
    return {"ran": True, "all_match": ok, "checks": rows}


# --------------------------------------------------------------------------
# figure
# --------------------------------------------------------------------------


def make_figure(fire: dict, rowset: str, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for cand in ("NanumGothic", "Malgun Gothic", "AppleGothic", "Noto Sans CJK KR"):
        if any(cand in f.name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = cand
            break
    plt.rcParams["axes.unicode_minus"] = False

    us = _step_rows(fire, rowset)
    fig = plt.figure(figsize=(10.5, 4.6))
    fig.suptitle(f"{fire['fire_id']} — 관측 확산 방위 · ERA5 바람 · 사면 상승 방위",
                 fontsize=12)

    ax = fig.add_subplot(1, 2, 1, projection="polar")
    ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
    if us:
        ob = np.radians([s["rowsets"][rowset]["bearing_centroid_deg"] for s in us])
        rr = [s["rowsets"][rowset]["R_centroid"] for s in us]
        wi = np.radians([s["wind"]["wind_vector_mean_deg"] for s in us])
        up = np.radians([s["rowsets"][rowset]["upslope_bearing_smooth1500_deg"]
                         for s in us])
        ax.scatter(ob, rr, s=72, marker="o", color="#1f77b4",
                   edgecolor="white", linewidth=0.6, zorder=3, label="관측 확산")
        ax.scatter(wi, rr, s=72, marker="X", color="#d62728",
                   edgecolor="white", linewidth=0.6, zorder=3, label="ERA5 바람")
        ax.scatter(up, rr, s=76, marker="^", color="#2ca02c",
                   edgecolor="white", linewidth=0.6, zorder=3, label="사면 상승")
        ax.legend(loc="upper right", bbox_to_anchor=(1.32, 1.13), fontsize=8,
                  framealpha=0.9)
    ax.set_ylim(0, 1)
    ax.set_title("방위 (반지름 = 방향 집중도 R)", fontsize=9, pad=16)
    ax.tick_params(labelsize=8)

    ax2 = fig.add_subplot(1, 2, 2)
    if us:
        labels = ["ERA5 바람\n(구간 벡터평균)", "사면 상승\n(1.5 km 평활)"]
        vals = [
            float(np.mean([s["rowsets"][rowset]["obs_vs_wind_vector_mean_deg"]
                           for s in us])),
            float(np.mean([s["rowsets"][rowset]["obs_vs_upslope_smooth1500_deg"]
                           for s in us])),
        ]
        bars = ax2.bar(labels, vals, color=["#d62728", "#2ca02c"], width=0.55)
        ax2.axhline(90, ls="--", lw=1.2, color="grey")
        ax2.text(1.42, 92, "90° = 무관계", fontsize=8, color="grey", ha="right")
        for bar, v in zip(bars, vals):
            ax2.text(bar.get_x() + bar.get_width() / 2, v + 3, f"{v:.1f}°",
                     ha="center", fontsize=10, fontweight="bold")
        ax2.set_ylim(0, 130)
    ax2.set_ylabel("관측 방위와의 평균 각도차 (°)", fontsize=9)
    ax2.set_title("작을수록 잘 맞습니다", fontsize=9)
    ax2.tick_params(labelsize=8)
    ax2.spines[["top", "right"]].set_visible(False)

    fig.tight_layout(rect=(0, 0, 1, 0.90))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def make_summary_figure(payload: dict, rowset: str, path: Path) -> None:
    """The honest overview: per fire, sized by evidence, with the reversal shown.

    A single per-fire figure can only flatter whichever fire it shows. Pooled,
    upslope beats wind; averaged over folds, wind beats upslope — because two
    fires supply 28 of 36 steps and those are the two where upslope does well.
    A summary that hides that reversal would be the most misleading figure in
    the project, so the reversal IS the figure.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    for cand in ("Noto Sans CJK KR", "NanumGothic", "Malgun Gothic", "AppleGothic"):
        if any(cand in f.name for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = cand
            break
    plt.rcParams["axes.unicode_minus"] = False

    pf = payload["rowsets"][rowset]["per_fire"]
    pooled = payload["rowsets"][rowset]["pooled"]
    fires = sorted(pf, key=lambda k: -pf[k]["n_usable_steps"])
    x = np.arange(len(fires))
    wind = [pf[f]["mean_abs_angle"]["wind_vector_mean"] for f in fires]
    up = [pf[f]["mean_abs_angle"]["upslope_smooth1500"] for f in fires]
    ns = [pf[f]["n_usable_steps"] for f in fires]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 4.8),
                                  gridspec_kw={"width_ratios": [2.1, 1]})
    fig.suptitle("관측 확산 방위는 무엇을 따르는가 — 화재별, 그리고 통합", fontsize=13)

    ax.bar(x - 0.2, wind, 0.4, color="#d62728", label="ERA5 바람 (구간 벡터평균)")
    ax.bar(x + 0.2, up, 0.4, color="#2ca02c", label="사면 상승 (1.5 km 평활)")
    ax.axhline(90, ls="--", lw=1.2, color="grey")
    ax.text(-0.45, 92.5, "90° = 무관계", fontsize=8, color="grey", ha="left",
            bbox=dict(facecolor="white", edgecolor="none", pad=1.2, alpha=0.85))
    ax.set_xticks(x)
    ax.set_xticklabels([f"{f}\n({n}스텝)" for f, n in zip(fires, ns)], fontsize=7.5)
    ax.set_ylabel("관측 방위와의 평균 각도차 (°)  ↓ 작을수록 일치", fontsize=9)
    ax.set_ylim(0, 190)
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title("화재별 — 스텝 수가 크게 다릅니다", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)

    pooled_w = pooled["drivers"]["wind_vector_mean"]["mean_abs_angle_deg"]
    pooled_u = pooled["drivers"]["upslope_smooth1500"]["mean_abs_angle_deg"]
    fold_w = pooled["fold_spread_of_mean_angle"]["wind_vector_mean"]["mean"]
    fold_u = pooled["fold_spread_of_mean_angle"]["upslope_smooth1500"]["mean"]
    xx = np.arange(2)
    ax2.bar(xx - 0.2, [pooled_w, fold_w], 0.4, color="#d62728", label="ERA5 바람")
    ax2.bar(xx + 0.2, [pooled_u, fold_u], 0.4, color="#2ca02c", label="사면 상승")
    ax2.axhline(90, ls="--", lw=1.2, color="grey")
    ax2.set_xticks(xx)
    ax2.set_xticklabels(["통합\n(스텝 가중)", "폴드 평균\n(화재 1표씩)"], fontsize=8.5)
    ax2.set_ylim(0, 190)
    ax2.set_title("⚠ 집계 방식에 따라 순서가 뒤집힙니다", fontsize=10)
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.tick_params(labelsize=8)
    for i, (a, b) in enumerate(((pooled_w, pooled_u), (fold_w, fold_u))):
        ax2.text(i - 0.2, a + 4, f"{a:.0f}°", ha="center", fontsize=9, fontweight="bold")
        ax2.text(i + 0.2, b + 4, f"{b:.0f}°", ha="center", fontsize=9, fontweight="bold")

    fig.tight_layout(rect=(0, 0, 1, 0.91))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    committed = json.loads(
        (REPO / "data/processed/spread_v2_lofo.json").read_text(encoding="utf-8"))
    fire_ids = sorted(committed["per_fire_auc"])

    model_pos = model_positive_cells(fire_ids)
    fires = [analyse_fire(f, model_pos) for f in fire_ids]

    check = session10_check(fires)
    payload = {
        "schema_version": 1,
        "title": "Direction drivers — wind sampling, row set, and terrain",
        "provenance": "derived",
        "arm": "A_geometry",
        "generated_by": "scripts/direction_drivers.py",
        "min_new_cells_threshold": MIN_NEW_CELLS,
        "usable_criterion": "identical to scripts/label_geometry.py — n_new_cells "
                            f">= {MIN_NEW_CELLS} on the ALL-cells row set",
        "dem_smoothing_windows_m": list(SMOOTH_WINDOWS_M),
        "dem_smoothing_effective": effective_windows(),
        "dem_nodata_fill": ("nearest-valid; SRTM carries 0-2.8% nodata and a "
                            "boxcar spreads each NaN across its window"),
        "valley_window_m": VALLEY_WINDOW_M,
        "session10_consistency": check,
        "rowsets": {rs: {**summarise(fires, rs),
                         "bearing_persistence": persistence(fires, rs),
                         "slope_conditioning": slope_conditioning(fires, rs)}
                    for rs in ("all", "model")},
        "fires": fires,
    }

    if args.write:
        OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        for f in fires:
            make_figure(f, "all", FIGDIR / f"direction_drivers_{f['fire_id']}.png")
        make_summary_figure(payload, "all", FIGDIR / "direction_drivers_summary.png")
        print(f"wrote {OUT_JSON.relative_to(REPO)} and {len(fires) + 1} figures")

    print("\n=== Session 10 consistency ===")
    if check.get("ran"):
        for k, v in check["checks"].items():
            flag = "ok " if v["matches"] else "MISMATCH"
            print(f"  {flag} {k:34s} s10={v['session10']}  s11={v['session11']}")
    for rs in ("all", "model"):
        p = payload["rowsets"][rs]["pooled"]
        print(f"\n=== rowset={rs}  n_usable={p['n_usable_steps']}  "
              f"R={p['R_centroid']['mean']}  slope={p['mean_slope_deg']['mean']}deg ===")
        for k, v in p["drivers"].items():
            print(f"  {k:22s} mean_angle={v['mean_abs_angle_deg']}deg "
                  f"sd={v['sd_deg']} circ_corr={v['circ_corr']} n={v['n']}")
        va = p["valley_axis"]
        print(f"  {'valley_axis (AXIAL)':22s} mean_axial={va['mean_abs_axial_deg']}deg "
              f"(chance 45) circ_corr_axial={va['circ_corr_axial']}")
        print(f"  persistence: {payload['rowsets'][rs]['bearing_persistence']}")
        print(f"  slope_conditioning: "
              f"{json.dumps(payload['rowsets'][rs]['slope_conditioning'])[:400]}")

    if check.get("ran") and not check.get("all_match"):
        print("\nSTOP: this analysis does not reproduce Session 10 under Session 10's "
              "settings. The hardening cannot be trusted until that is explained.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
