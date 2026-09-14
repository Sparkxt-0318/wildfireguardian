#!/usr/bin/env python
"""Build the K-SPREAD-2025 Stage 2 proxy entrants E1 (wind-cone) and E2 (Rothermel-family).

Rule, declared before this ran: ``docs/benchmark/stage2_proxy_rules.md``. Brief:
``docs/auto/briefs/K_SPREAD_STAGE2.md``. Protocol: ``docs/benchmark/K_SPREAD_2025.md`` v0.1.

Both proxies advance the T0 detection footprint of the committed canonical npz. Their wind
is NOT known on this machine (no ERA5, no 산악기상 pull, no KMA archive, no key --- see the
Stage 2 report §2), so neither is built at one wind. Each is swept over the declared grid
of 36 bearings x 20 head rates and the grid point that scores best against the observation
is written as an **oracle** entrant: an upper bound on what that method class could have
done on this fire under ANY wind, declared HINDCAST track because the choice reads the
observation. The forecast-track E1 and E2 the brief asked for remain NOT RUN.

E1 and E2 differ by exactly one term, which is the whole point of the pair: they share the
same least-time propagation and E2 alone multiplies the cone's rate by Rothermel's upslope
factor, taken on the committed DEM snapshot.

    python scripts/benchmark/build_entrants_stage2.py
    python scripts/benchmark/build_entrants_stage2.py --quick   # coarse grid, for tests
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kspread_metrics import auc_iou_at_horizon  # noqa: E402
from kspread_truth import first_seen_grid  # noqa: E402

OUT = REPO / "data/processed/benchmark/entrants"
SWEEP_OUT = REPO / "data/processed/benchmark/stage2_sweep.json"
CANON_NPZ = REPO / "data/processed/routing_demo_canonical.npz"
DEM = REPO / "data/snapshots/srtm-dem_yeongdeok-2025_20260723_66988bf5.tif"
EVENT = "yeongdeok_2025"

# --- the declared construction (docs/benchmark/stage2_proxy_rules.md §2) --------------
BACKING = 0.15                    # backing-fire fraction of the head rate
SMOOTH_SIGMA_M = 2000.0           # the 읍면동 scale; not swept
BETA = 0.05                       # forest-litter packing ratio -> phi_s coefficient 12.34
SLOPE_COEF = 5.275 * BETA ** -0.3
TIMES_MIN = np.arange(0.0, 720.0 + 1e-9, 30.0)     # protocol §6's 30-minute step
HORIZONS = (180.0, 300.0, 480.0)                   # protocol §2
# --- the declared sweep (§3) ----------------------------------------------------------
BEARINGS = np.arange(0.0, 360.0, 10.0)             # 36 wind-toward bearings
RATES = np.arange(100.0, 2000.0 + 1e-9, 100.0)     # 20 head rates, m per 30 min


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def canvas():
    """Canvas geometry, the T0 seed and the observation, all from the committed npz."""
    z = np.load(CANON_NPZ)
    x0, y0, x1, y1, cell = [float(v) for v in z["grid_extent"]]
    nrow, ncol = z["obs_stack"].shape[1:]
    xs = x0 + (np.arange(ncol) + 0.5) * cell
    ys = y1 - (np.arange(nrow) + 0.5) * cell          # row 0 is the north edge
    return dict(z=z, x0=x0, y0=y0, x1=x1, y1=y1, cell=cell, nrow=nrow, ncol=ncol,
                X=np.broadcast_to(xs, (nrow, ncol)).copy(),
                Y=np.broadcast_to(ys[:, None], (nrow, ncol)).copy(),
                seed=z["obs_stack"][0].astype(bool))


def elevation_on_canvas(cv) -> tuple[np.ndarray, np.ndarray]:
    """Elevation resampled to the 500 m canvas, and the mask of cells the DEM covers."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    dst = np.full((cv["nrow"], cv["ncol"]), np.nan, np.float32)
    with rasterio.open(DEM) as src:
        transform = rasterio.transform.from_origin(cv["x0"], cv["y1"], cv["cell"], cv["cell"])
        reproject(source=rasterio.band(src, 1), destination=dst,
                  dst_transform=transform, dst_crs="EPSG:5179",
                  dst_nodata=np.nan, resampling=Resampling.average)
    covered = np.isfinite(dst)
    return np.where(covered, dst, 0.0).astype(np.float64), covered


def _neighbour_offsets():
    return [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]


def cone_rate(bearing_deg: float, ex: float, ey: float, length: float) -> float:
    """The cone's rate in the travel direction as a fraction of the head rate.

    ``max(BACKING, cos Δ)`` --- the full head rate straight downwind, a cosine falloff to the
    flanks, and the 0.15 backing floor behind. Shared by E1 and E2 so the pair differs by the
    slope term alone.
    """
    th = np.deg2rad(bearing_deg)
    cosd = (ex * np.sin(th) + ey * np.cos(th)) / length
    return max(BACKING, float(cosd))


def unit_cost(cv, bearing_deg: float, elev: np.ndarray | None) -> np.ndarray:
    """Minutes to reach each cell at a head rate of 1 m per 30 min, as a least-time path.

    Edge a->b costs ``30 * len / (max(BACKING, cos Δ) * (1 + φ_s))`` minutes, with
    ``φ_s = 5.275 β^-0.3 (tan s)²`` on the UPSLOPE only (Rothermel's slope factor is an
    upslope term; descending travel gets φ_s = 0). A virtual source joins every T0 cell at
    zero cost, so one single-source Dijkstra serves all 249 seeds.

    ``elev=None`` is **E1**: no terrain term at all, φ_s = 0 everywhere. A real ``elev`` is
    **E2**. The two therefore share every line of propagation and differ by the slope factor
    alone, which is the only reason their gap can be read as what that factor buys.

    ⚠ **The 8-connected grid is generous crosswind, for both entrants equally.** A front
    restricted to eight directions can zigzag --- alternating two well-aligned headings ---
    and so reach a crosswind cell sooner than a strict straight-line cone would. Measured on
    a flat test canvas the shortfall against a straight ray reaches 23 % due crosswind. It is
    an artefact of the discretisation, not of either method; it raises both ceilings, which
    is the harmless direction for a bound, and it cancels in the E1-E2 comparison because
    both walk the same graph.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra

    nrow, ncol, cell = cv["nrow"], cv["ncol"], cv["cell"]
    n = nrow * ncol
    idx = np.arange(n).reshape(nrow, ncol)
    rows, cols, vals = [], [], []
    flat = elev is None
    z = (np.zeros(n) if flat else elev.ravel())
    for dr, dc in _neighbour_offsets():
        a = idx[max(0, -dr):nrow - max(0, dr), max(0, -dc):ncol - max(0, dc)]
        b = idx[max(0, dr):nrow - max(0, -dr), max(0, dc):ncol - max(0, -dc)]
        ex, ey = dc * cell, -dr * cell                 # +row is south, so dy = -dr*cell
        length = float(np.hypot(ex, ey))
        rate = cone_rate(bearing_deg, ex, ey, length)
        if flat:
            speed = np.full(a.size, rate)
        else:
            tan_s = np.maximum(z[b.ravel()] - z[a.ravel()], 0.0) / length   # upslope only
            speed = rate * (1.0 + SLOPE_COEF * tan_s ** 2)
        rows.append(a.ravel()); cols.append(b.ravel())
        vals.append(30.0 * length / speed)
    src = n
    sr, sc = np.nonzero(cv["seed"])
    seeds = idx[sr, sc]
    rows.append(np.full(seeds.size, src)); cols.append(seeds)
    vals.append(np.zeros(seeds.size))
    g = coo_matrix((np.concatenate(vals),
                    (np.concatenate(rows), np.concatenate(cols))), shape=(n + 1, n + 1)).tocsr()
    d = dijkstra(g, directed=True, indices=src)[:n]
    return d.reshape(nrow, ncol)


def stack_from_unit_cost(cv, unit_min: np.ndarray, rate: float,
                         times=TIMES_MIN) -> np.ndarray:
    """Footprints at each time, 읍면동-smoothed, with the footprint itself kept certain."""
    from scipy.ndimage import gaussian_filter

    sigma_cells = SMOOTH_SIGMA_M / cv["cell"]
    arrival = unit_min / rate
    out = np.empty((len(times), cv["nrow"], cv["ncol"]), np.float32)
    for k, t in enumerate(times):
        binary = (arrival <= t) | cv["seed"]
        blur = gaussian_filter(binary.astype(np.float32), sigma_cells, mode="constant")
        out[k] = np.maximum(binary.astype(np.float32), blur)
    return out


def sweep(cv, kind: str, elev, bearings, rates, fs, t) -> list[dict]:
    """Mean ROC-AUC and mean IoU over the three horizons at every declared grid point."""
    rows = []
    for j, bg in enumerate(bearings):
        unit = unit_cost(cv, bg, None if kind == "e1" else elev)
        print(f"  [{kind}] bearing {bg:5.1f}° ({j + 1}/{len(bearings)})", flush=True)
        for r in rates:
            stack = stack_from_unit_cost(cv, unit, r, HORIZONS)
            aucs, ious = [], []
            for k, h in enumerate(HORIZONS):
                m = auc_iou_at_horizon(stack[k:k + 1], np.array([h]), fs, t, h, m=0)
                aucs.append(m["roc_auc"]); ious.append(m["iou_at_p_ge_0.5"])
            rows.append({"bearing_deg": float(bg), "head_rate_m_per_30min": float(r),
                         "roc_auc": [float(a) for a in aucs],
                         "iou_at_p_ge_0.5": [float(i) for i in ious],
                         "mean_roc_auc": float(np.mean(aucs)),
                         "mean_iou": float(np.mean(ious))})
    return rows


def write_entrant(entrant: dict, extent, times, stack) -> Path:
    d = OUT / entrant["id"]
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{EVENT}.npz"
    np.savez_compressed(p, grid_extent=np.asarray(extent, float),
                        times_min=np.asarray(times, float), stack=stack.astype(np.float32))
    entrant["events"] = {EVENT: {"npz": str(p.relative_to(REPO)), "sha256": sha256(p)}}
    entrant["generated_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entrant["git_commit"] = _commit()
    (d / "entrant.json").write_text(json.dumps(entrant, indent=1, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="coarse grid (tests); not the declared sweep")
    args = ap.parse_args()

    bearings = BEARINGS[::6] if args.quick else BEARINGS
    rates = RATES[::5] if args.quick else RATES

    cv = canvas()
    fs, t = first_seen_grid(cv["z"])
    elev, covered = elevation_on_canvas(cv)
    print(f"canvas {cv['nrow']}x{cv['ncol']} @ {cv['cell']:.0f} m; T0 seed {int(cv['seed'].sum())} cells; "
          f"DEM covers {int(covered.sum())}/{covered.size} ({100 * covered.mean():.1f}%)", flush=True)

    extent = [cv["x0"], cv["y0"], cv["x1"], cv["y1"], cv["cell"]]
    results = {}
    for kind, pe, label, what in (
        ("e1", "E1", "E1 wind-cone oracle (upper bound)",
         "the T0 footprint advanced along a swept wind at a fixed rate per 30 min, no terrain "
         "term, 읍면동-scale smoothing; the G-DAPS class of method as described in press, not G-DAPS"),
        ("e2", "E2", "E2 Rothermel-family oracle (upper bound)",
         "E1's cone multiplied by Rothermel's upslope factor on the committed DEM, uniform "
         "fuel; the class of the 2003-lineage national system, not NIFoS's implementation"),
    ):
        print(f"sweeping {kind}: {len(bearings)} bearings x {len(rates)} rates", flush=True)
        rows = sweep(cv, kind, elev, bearings, rates, fs, t)
        best_auc = max(rows, key=lambda r: r["mean_roc_auc"])
        best_iou = max(rows, key=lambda r: r["mean_iou"])
        results[kind] = {"grid_points": len(rows), "rows": rows,
                         "selected_primary_mean_roc_auc": best_auc,
                         "selected_secondary_mean_iou": best_iou}
        same = (best_iou["bearing_deg"] == best_auc["bearing_deg"]
                and best_iou["head_rate_m_per_30min"] == best_auc["head_rate_m_per_30min"])
        results[kind]["both_criteria_select_the_same_grid_point"] = bool(same)
        picks = [("", best_auc, "max mean ROC-AUC over the three horizons")]
        if not same:
            picks.append(("_iou", best_iou, "max mean IoU at p >= 0.5 over the three horizons"))
        else:
            print(f"  [{kind}] both criteria select the same grid point; one bundle written")
        for tag, sel, crit in picks:
            unit = unit_cost(cv, sel["bearing_deg"], None if kind == "e1" else elev)
            stack = stack_from_unit_cost(cv, unit, sel["head_rate_m_per_30min"])
            above = stack[-1] >= 0.5
            outside = int((above & ~covered).sum())
            ent = {
                "id": f"{kind}_{'windcone' if kind == 'e1' else 'rothermel'}_oracle{tag}",
                "protocol_entrant": pe, "name": label + (" [IoU-selected]" if tag else ""),
                "protocol_version": "v0.1", "track": "hindcast", "resolution_m": cv["cell"],
                "inputs_used": ["FIRMS cumulative detections at T0"]
                + ([] if kind == "e1" else ["SRTM DEM (committed snapshot)"])
                + ["wind selected against the observation (oracle)"],
                "track_reason": (
                    "The wind is not an input on this machine; it is SELECTED as the grid point "
                    "that scores best against the observed footprint, which is an observation "
                    "after T0. Protocol §3 puts that in the hindcast track. This is an UPPER "
                    "BOUND on the method class, not a score it achieved: the forecast-track E1 "
                    "and E2 are NOT RUN (docs/benchmark/stage2_proxy_rules.md §1)."),
                "what_it_is": what,
                "oracle": {
                    "selection_criterion": crit,
                    "rule_page": "docs/benchmark/stage2_proxy_rules.md",
                    "grid_points_searched": len(rows),
                    "bearing_deg": sel["bearing_deg"],
                    "head_rate_m_per_30min": sel["head_rate_m_per_30min"],
                    "mean_roc_auc_at_selection": sel["mean_roc_auc"],
                    "mean_iou_at_selection": sel["mean_iou"]},
                "construction": {
                    "backing_fraction": BACKING, "smoothing_sigma_m": SMOOTH_SIGMA_M,
                    "slope_factor": ("none (E1 carries no terrain term)" if kind == "e1"
                                     else f"5.275*beta^-0.3*(tan s)^2, beta={BETA} -> {SLOPE_COEF:.2f}, upslope only"),
                    "fuel": "uniform (임상도 1:5000 not on this machine)",
                    "times_min": [float(v) for v in TIMES_MIN]},
                "provenance": {
                    "seed_source": "data/processed/routing_demo_canonical.npz",
                    "seed_array": "obs_stack[0]",
                    "seed_sha256": sha256(CANON_NPZ),
                    "t0_cells": int(cv["seed"].sum()),
                    "dem": (None if kind == "e1" else str(DEM.relative_to(REPO))),
                    "dem_sha256": (None if kind == "e1" else sha256(DEM)),
                    "dem_cells_covered": int(covered.sum()),
                    "dem_cells_total": int(covered.size),
                    "cells_above_p_cut_outside_dem_coverage": outside},
                "built_by": "scripts/benchmark/build_entrants_stage2.py",
            }
            d = write_entrant(ent, extent, TIMES_MIN, stack)
            print(f"  wrote {d.relative_to(REPO)}  bearing {sel['bearing_deg']:.0f}° "
                  f"rate {sel['head_rate_m_per_30min']:.0f} m/30min", flush=True)

    SWEEP_OUT.parent.mkdir(parents=True, exist_ok=True)
    SWEEP_OUT.write_text(json.dumps({
        "schema_version": 1,
        "title": "K-SPREAD-2025 Stage 2 proxy wind sweep",
        "rule_page": "docs/benchmark/stage2_proxy_rules.md",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _commit(),
        "quick": bool(args.quick),
        "grid": {"bearings_deg": [float(b) for b in bearings],
                 "head_rates_m_per_30min": [float(r) for r in rates]},
        "horizons_min": list(HORIZONS),
        "construction": {"backing_fraction": BACKING, "smoothing_sigma_m": SMOOTH_SIGMA_M,
                         "slope_coefficient": SLOPE_COEF, "beta": BETA},
        "dem_coverage": {"cells_covered": int(covered.sum()), "cells_total": int(covered.size)},
        "entrants": results,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {SWEEP_OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
