"""Deliverable 2 -- per-candidate-cell feature extraction.

At each overpass->overpass transition we take every currently-unburned cell
within ``candidate_radius`` of the active fire as a *candidate*, label it 1 if
it becomes burned by the next overpass else 0, and compute physically-grounded
features. Every feature encodes a known fire-spread mechanism (proximity,
observed intensity, upslope preference, fuel, growth-direction); there are no
opaque features.

Leakage discipline: every feature uses information available at or before the
transition start ``t`` only. In particular the "directional spread" proxy is
derived from the fire's *past* growth (cells burned at epoch t vs earlier),
never from the t+1 target.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import ndimage

from .config import PipelineConfig
from .grid import FireGridSequence

# WorldCover classes we expose as one-hot fuel indicators (mechanistically
# distinct fire behaviour: timber crown vs shrub vs cured grass vs cropland).
FUEL_INDICATORS = {"fuel_tree": 10, "fuel_shrub": 20, "fuel_grass": 30, "fuel_crop": 40}

FEATURE_COLUMNS = [
    # proximity / fire geometry
    "dist_to_nearest_burning_m",
    "n_burning_within_500m",
    "n_burning_within_1000m",
    # observed intensity (VIIRS FRP)
    "frp_sum_1000m",
    "frp_max_1000m",
    "nearest_burning_frp",
    # terrain
    "slope_deg",
    "slope_alignment",
    "elevation_rel_m",
    # fuel  (is_burnable itself is NOT a model feature: it is the HARD GATE
    # applied during candidate selection, after which it is constant 1.0 for
    # every fuel-covered candidate. The informative fuel signal is the local
    # burnable fraction and the cover-class one-hots.)
    "burnable_frac_nbhd_1000m",
    *FUEL_INDICATORS.keys(),
    # data-derived directionality (NOT a weather input)
    "directional_alignment",
]


def _disk_kernel(radius_m: float, cell: float) -> np.ndarray:
    r = int(round(radius_m / cell))
    if r < 1:
        return np.ones((1, 1))
    yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
    return ((xx**2 + yy**2) <= r**2).astype(float)


def _centroid(mask: np.ndarray):
    if not mask.any():
        return None
    rr, cc = np.nonzero(mask)
    return rr.mean(), cc.mean()


def transition_table(
    seq: FireGridSequence, t: int, config: PipelineConfig
) -> tuple[pd.DataFrame | None, dict]:
    """Build the labelled candidate table for the transition t -> t+1.

    Returns (dataframe_or_None, diagnostics).
    """
    cell = seq.cell_size_m
    burned_t = seq.burned_mask(t)
    burned_t1 = seq.burned_mask(t + 1)
    land = seq.land_mask()
    diag = {"fire_id": seq.fire_id, "transition": t, "n_burning_t": int(burned_t.sum())}

    if burned_t.sum() == 0:
        diag.update(n_candidates=0, n_positive=0, capture_rate=None)
        return None, diag

    # Distance to nearest burning cell + index of that nearest cell.
    dist_cells, (iy, ix) = ndimage.distance_transform_edt(~burned_t, return_indices=True)
    dist_m = dist_cells * cell

    # Candidate mask.
    cand = (~burned_t) & land & (dist_m <= config.candidate_radius_m)
    # HARD GATE: drop *known* non-burnable cells; keep unknown-fuel (NaN) cells.
    known_nonburnable = seq.is_burnable == 0
    cand = cand & ~known_nonburnable

    new_ignitions = burned_t1 & (~burned_t) & land
    # capture rate: fraction of true new ignitions that are candidates
    n_new = int(new_ignitions.sum())
    captured = int((new_ignitions & cand).sum())
    diag["n_new_ignitions"] = n_new
    diag["capture_rate"] = (captured / n_new) if n_new else None

    if not cand.any():
        diag.update(n_candidates=0, n_positive=0)
        return None, diag

    rr, cc = np.nonzero(cand)

    # --- proximity / geometry ---
    dist_sel = dist_m[rr, cc]
    k500 = _disk_kernel(500.0, cell)
    k1000 = _disk_kernel(1000.0, cell)
    burned_f = burned_t.astype(float)
    n500 = ndimage.convolve(burned_f, k500, mode="constant")[rr, cc]
    n1000 = ndimage.convolve(burned_f, k1000, mode="constant")[rr, cc]

    # --- observed intensity ---
    frp_t = seq.frp_at(t)
    frp_sum = ndimage.convolve(frp_t, k1000, mode="constant")[rr, cc]
    frp_max = ndimage.maximum_filter(frp_t, footprint=k1000, mode="constant")[rr, cc]
    nearest_frp = seq.cell_frp[iy, ix][rr, cc]

    # --- terrain ---
    slope_sel = seq.slope_deg[rr, cc]
    nearest_elev = seq.elevation[iy, ix][rr, cc]
    elev_rel = seq.elevation[rr, cc] - nearest_elev
    # fire -> cell unit vector (east, north)
    ve = (cc - ix[rr, cc]).astype(float)
    vn = (iy[rr, cc] - rr).astype(float)  # north increases as row decreases
    vmag = np.hypot(ve, vn)
    with np.errstate(invalid="ignore", divide="ignore"):
        ve_u = np.where(vmag > 0, ve / vmag, 0.0)
        vn_u = np.where(vmag > 0, vn / vmag, 0.0)
    slope_align = seq.uphill_e[rr, cc] * ve_u + seq.uphill_n[rr, cc] * vn_u

    # --- fuel ---
    is_burn_sel = seq.is_burnable[rr, cc]
    bf_num = ndimage.convolve(np.nan_to_num(seq.burnable_frac_cell), k1000, mode="constant")
    bf_den = ndimage.convolve(seq.fuel_covered.astype(float), k1000, mode="constant")
    with np.errstate(invalid="ignore", divide="ignore"):
        bf_nbhd_full = np.where(bf_den > 0, bf_num / bf_den, np.nan)
    bf_nbhd = bf_nbhd_full[rr, cc]
    fuel_class_sel = seq.fuel_class[rr, cc]
    fuel_onehot = {
        name: np.where(np.isfinite(fuel_class_sel), (np.round(fuel_class_sel) == code).astype(float), np.nan)
        for name, code in FUEL_INDICATORS.items()
    }

    # --- directional spread proxy (past growth only) ---
    prev = seq.burn_overpass == (t - 1) if t >= 1 else np.zeros_like(burned_t)
    recent = seq.burn_overpass == t
    c_recent = _centroid(recent if recent.any() else burned_t)
    c_prev = _centroid(prev) if prev.any() else _centroid(burned_t & ~recent)
    if c_recent is not None and c_prev is not None:
        de = c_recent[1] - c_prev[1]  # east (col)
        dn = c_prev[0] - c_recent[0]  # north (row decreasing)
        dmag = np.hypot(de, dn)
        if dmag > 0:
            de, dn = de / dmag, dn / dmag
            dir_align = de * ve_u + dn * vn_u
        else:
            dir_align = np.zeros(len(rr))
    else:
        dir_align = np.zeros(len(rr))

    data = {
        "dist_to_nearest_burning_m": dist_sel,
        "n_burning_within_500m": n500,
        "n_burning_within_1000m": n1000,
        "frp_sum_1000m": frp_sum,
        "frp_max_1000m": frp_max,
        "nearest_burning_frp": nearest_frp,
        "slope_deg": slope_sel,
        "slope_alignment": slope_align,
        "elevation_rel_m": elev_rel,
        "is_burnable": is_burn_sel,
        "burnable_frac_nbhd_1000m": bf_nbhd,
        **fuel_onehot,
        "directional_alignment": dir_align,
        "label": burned_t1[rr, cc].astype(int),
        "fire_id": seq.fire_id,
        "transition": t,
        "row": rr,
        "col": cc,
    }
    df = pd.DataFrame(data)
    diag.update(n_candidates=len(df), n_positive=int(df["label"].sum()))
    return df, diag


def build_fire_features(
    seq: FireGridSequence, config: PipelineConfig
) -> tuple[pd.DataFrame, list[dict]]:
    frames, diags = [], []
    for t in range(seq.n_overpasses - 1):
        df, d = transition_table(seq, t, config)
        diags.append(d)
        if df is not None and len(df):
            frames.append(df)
    if frames:
        out = pd.concat(frames, ignore_index=True)
    else:
        out = pd.DataFrame(columns=FEATURE_COLUMNS + ["label", "fire_id", "transition", "row", "col"])
    return out, diags
